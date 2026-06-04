"""
Duplicate task detection and merge-request flow.

Flow:
  1. Developer opens dashboard → GET /tracker/duplicates/my-groups
       - Finds all tasks assigned to developer with embeddings
       - Clusters tasks with cosine similarity >= SIMILARITY_THRESHOLD
       - Creates/refreshes TrackerDuplicateGroup records
       - Returns grouped results (does NOT show if group status is kept/merged)

  2. Developer keeps all → POST /tracker/duplicates/{group_id}/keep
       - Marks group status = "kept", logs activity

  3. Developer requests merge → POST /tracker/duplicates/{group_id}/merge-request
       - Creates TrackerMergeRequest
       - Notifies all creators (managers) of tasks in the group

  4. Manager approves → POST /tracker/duplicates/merge-requests/{request_id}/approve
       - Primary task stays active, all other tasks → status = "rejected"
       - Logs activity on every task, notifies developer

  5. Manager rejects → POST /tracker/duplicates/merge-requests/{request_id}/reject
       - Group status = "rejected", developer continues all tasks
       - Notifies developer
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from fastapi import HTTPException
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.similar_task import (
    TrackerDuplicateGroup, TrackerDuplicateGroupMember, TrackerMergeRequest,
)
from app.models.tracker.task import TrackerTask, TrackerTaskMember
from app.schemas.tracker.similar_task import (
    DuplicateGroupResponse, MergeRequestCreate, MergeRequestResponse,
    MergeRequestReview, TaskSnapshotInGroup,
)
from app.services.tracker.activity_service import log_activity
from app.services.tracker.notification_service import notify

SIMILARITY_THRESHOLD = 0.82  # cosine similarity — tasks above this are grouped


# ── helpers ───────────────────────────────────────────────────────────────────

async def _emp_name(db: AsyncSession, emp_id: uuid.UUID | None) -> str | None:
    if not emp_id:
        return None
    result = await db.execute(select(Employee).where(Employee.id == emp_id))
    emp = result.scalars().first()
    return (emp.full_name or emp.email) if emp else None


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom else 0.0


def _cluster_tasks(tasks: list[TrackerTask]) -> list[list[tuple[TrackerTask, float]]]:
    """
    Single-pass greedy clustering.
    Returns list of groups; each group is a list of (task, score_vs_first).
    Groups with only one task are excluded.
    """
    assigned = set()
    groups: list[list[tuple[TrackerTask, float]]] = []

    for i, task in enumerate(tasks):
        if i in assigned or not task.task_vector:
            continue
        group: list[tuple[TrackerTask, float]] = [(task, 1.0)]
        for j, other in enumerate(tasks):
            if j <= i or j in assigned or not other.task_vector:
                continue
            score = _cosine(task.task_vector, other.task_vector)
            if score >= SIMILARITY_THRESHOLD:
                group.append((other, round(score, 4)))
                assigned.add(j)
        if len(group) > 1:
            assigned.add(i)
            groups.append(group)

    return groups


async def _build_group_response(
    db: AsyncSession,
    group: TrackerDuplicateGroup,
) -> DuplicateGroupResponse:
    snapshots: list[TaskSnapshotInGroup] = []
    for member in group.members:
        t_res = await db.execute(select(TrackerTask).where(TrackerTask.id == member.task_id))
        task = t_res.scalars().first()
        if not task:
            continue
        snapshots.append(TaskSnapshotInGroup(
            task_id=task.id,
            title=task.title,
            status=task.status,
            priority=task.priority,
            deadline=task.deadline,
            created_by=task.created_by,
            creator_name=await _emp_name(db, task.created_by),
            similarity_score=member.similarity_score,
            role=member.role,
        ))

    # Fetch merge request if any
    mr_res = await db.execute(
        select(TrackerMergeRequest).where(TrackerMergeRequest.group_id == group.id)
    )
    mr = mr_res.scalars().first()
    merge_request: Optional[MergeRequestResponse] = None
    if mr:
        merge_request = MergeRequestResponse(
            id=mr.id,
            group_id=mr.group_id,
            requested_by=mr.requested_by,
            requester_name=await _emp_name(db, mr.requested_by),
            primary_task_id=mr.primary_task_id,
            reason=mr.reason,
            status=mr.status,
            reviewed_by=mr.reviewed_by,
            reviewer_name=await _emp_name(db, mr.reviewed_by),
            review_note=mr.review_note,
            created_at=mr.created_at,
            reviewed_at=mr.reviewed_at,
        )

    return DuplicateGroupResponse(
        id=group.id,
        developer_id=group.developer_id,
        label=group.label,
        status=group.status,
        tasks=snapshots,
        merge_request=merge_request,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


# ── public API ────────────────────────────────────────────────────────────────

async def get_my_duplicate_groups(
    db: AsyncSession,
    developer: Employee,
) -> list[DuplicateGroupResponse]:
    """
    Called when developer opens dashboard.
    Re-runs clustering on all active assigned tasks and upserts groups.
    Only returns groups with status 'open' or 'merge_requested'.
    """
    # Fetch all active tasks assigned to this developer
    member_result = await db.execute(
        select(TrackerTaskMember.task_id).where(TrackerTaskMember.employee_id == developer.id)
    )
    task_ids = list(member_result.scalars().all())

    if not task_ids:
        return []

    task_result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id.in_(task_ids),
            TrackerTask.organization_id == developer.organization_id,
            TrackerTask.status.notin_(["in_production", "rejected"]),
            TrackerTask.task_vector.is_not(None),
        )
    )
    tasks = task_result.scalars().all()

    if len(tasks) < 2:
        return []

    clusters = _cluster_tasks(list(tasks))

    # For each cluster, find or create a group
    # Match by the set of task_ids — if exact same set exists, reuse it
    for cluster in clusters:
        cluster_task_ids = frozenset(t.id for t, _ in cluster)

        # Find an existing open/merge_requested group with the same members
        existing_groups_result = await db.execute(
            select(TrackerDuplicateGroup).where(
                TrackerDuplicateGroup.developer_id == developer.id,
                TrackerDuplicateGroup.organization_id == developer.organization_id,
                TrackerDuplicateGroup.status.in_(["open", "merge_requested"]),
            )
        )
        existing_groups = existing_groups_result.scalars().all()

        matched_group: Optional[TrackerDuplicateGroup] = None
        for eg in existing_groups:
            existing_member_ids = frozenset(m.task_id for m in eg.members)
            if existing_member_ids == cluster_task_ids:
                matched_group = eg
                break

        if matched_group:
            matched_group.updated_at = datetime.now(timezone.utc)
        else:
            first_task = cluster[0][0]
            group = TrackerDuplicateGroup(
                organization_id=developer.organization_id,
                developer_id=developer.id,
                label=first_task.title,
                status="open",
            )
            db.add(group)
            await db.flush()

            for task, score in cluster:
                db.add(TrackerDuplicateGroupMember(
                    group_id=group.id,
                    task_id=task.id,
                    similarity_score=score if task.id != first_task.id else 1.0,
                    role="candidate",
                ))
            await db.flush()

    await db.commit()

    # Reload and return all open/merge_requested groups for this developer
    groups_result = await db.execute(
        select(TrackerDuplicateGroup).where(
            TrackerDuplicateGroup.developer_id == developer.id,
            TrackerDuplicateGroup.organization_id == developer.organization_id,
            TrackerDuplicateGroup.status.in_(["open", "merge_requested"]),
        ).order_by(TrackerDuplicateGroup.created_at.desc())
    )
    groups = groups_result.scalars().all()
    return [await _build_group_response(db, g) for g in groups]


async def keep_group(
    db: AsyncSession,
    group_id: uuid.UUID,
    developer: Employee,
) -> dict:
    """Developer chooses 'Keep All' — dismisses the duplicate group."""
    result = await db.execute(
        select(TrackerDuplicateGroup).where(
            TrackerDuplicateGroup.id == group_id,
            TrackerDuplicateGroup.developer_id == developer.id,
        )
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(404, "Duplicate group not found")
    if group.status not in ("open",):
        raise HTTPException(400, f"Group is already in status '{group.status}'")

    group.status = "kept"
    group.updated_at = datetime.now(timezone.utc)

    dev_name = developer.full_name or developer.email
    for member in group.members:
        await log_activity(
            db, member.task_id, "duplicate_group_kept",
            f"{dev_name} reviewed duplicate group and chose to keep all tasks separately.",
            developer.id,
        )

    await db.commit()
    return {"status": "kept", "group_id": str(group_id)}


async def request_merge(
    db: AsyncSession,
    group_id: uuid.UUID,
    payload: MergeRequestCreate,
    developer: Employee,
) -> MergeRequestResponse:
    """Developer submits a merge request for a duplicate group."""
    group_result = await db.execute(
        select(TrackerDuplicateGroup).where(
            TrackerDuplicateGroup.id == group_id,
            TrackerDuplicateGroup.developer_id == developer.id,
        )
    )
    group = group_result.scalars().first()
    if not group:
        raise HTTPException(404, "Duplicate group not found")
    if group.status != "open":
        raise HTTPException(400, f"Group is already in status '{group.status}'")

    # Validate primary_task_id is in the group
    member_ids = {m.task_id for m in group.members}
    if payload.primary_task_id not in member_ids:
        raise HTTPException(400, "primary_task_id must be one of the tasks in this group")

    # Verify primary task belongs to this org
    pt_result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == payload.primary_task_id,
            TrackerTask.organization_id == developer.organization_id,
        )
    )
    if not pt_result.scalars().first():
        raise HTTPException(404, "Primary task not found")

    mr = TrackerMergeRequest(
        group_id=group_id,
        requested_by=developer.id,
        primary_task_id=payload.primary_task_id,
        reason=payload.reason,
        status="pending",
    )
    db.add(mr)

    group.status = "merge_requested"
    group.updated_at = datetime.now(timezone.utc)

    await db.flush()

    dev_name = developer.full_name or developer.email

    # Collect all unique task creators (managers) to notify
    manager_ids: set[uuid.UUID] = set()
    task_titles: list[str] = []
    for member in group.members:
        t_res = await db.execute(select(TrackerTask).where(TrackerTask.id == member.task_id))
        task = t_res.scalars().first()
        if task:
            manager_ids.add(task.created_by)
            task_titles.append(f"• {task.title}")
            await log_activity(
                db, task.id, "merge_requested",
                f"{dev_name} submitted a merge request: {payload.reason}",
                developer.id,
            )

    manager_ids.discard(developer.id)
    task_list_str = "\n".join(task_titles)
    for mid in manager_ids:
        await notify(
            db, mid,
            "Merge Request from Developer",
            f"{dev_name} has requested to merge the following tasks:\n{task_list_str}\n\nReason: {payload.reason}",
            payload.primary_task_id,
        )

    await db.commit()
    await db.refresh(mr)

    return MergeRequestResponse(
        id=mr.id,
        group_id=mr.group_id,
        requested_by=mr.requested_by,
        requester_name=dev_name,
        primary_task_id=mr.primary_task_id,
        reason=mr.reason,
        status=mr.status,
        reviewed_by=None,
        reviewer_name=None,
        review_note=None,
        created_at=mr.created_at,
        reviewed_at=None,
    )


async def review_merge_request(
    db: AsyncSession,
    request_id: uuid.UUID,
    payload: MergeRequestReview,
    reviewer: Employee,
) -> MergeRequestResponse:
    """Manager approves or rejects a merge request."""
    mr_result = await db.execute(
        select(TrackerMergeRequest).where(TrackerMergeRequest.id == request_id)
    )
    mr = mr_result.scalars().first()
    if not mr:
        raise HTTPException(404, "Merge request not found")
    if mr.status != "pending":
        raise HTTPException(400, f"Merge request is already '{mr.status}'")

    group_result = await db.execute(
        select(TrackerDuplicateGroup).where(TrackerDuplicateGroup.id == mr.group_id)
    )
    group = group_result.scalars().first()
    if not group or group.organization_id != reviewer.organization_id:
        raise HTTPException(404, "Duplicate group not found")

    reviewer_name = reviewer.full_name or reviewer.email
    now = datetime.now(timezone.utc)

    mr.reviewed_by = reviewer.id
    mr.review_note = payload.note
    mr.reviewed_at = now

    if payload.action == "approve":
        mr.status = "approved"
        group.status = "merged"
        group.updated_at = now

        # Mark primary task member role, close all others
        for member in group.members:
            if member.task_id == mr.primary_task_id:
                member.role = "primary"
            else:
                member.role = "merged"
                # Close duplicate tasks
                t_res = await db.execute(
                    select(TrackerTask).where(TrackerTask.id == member.task_id)
                )
                task = t_res.scalars().first()
                if task and task.status not in ("in_production", "rejected"):
                    task.status = "rejected"
                    task.blocked_reason = f"Merged into task by {reviewer_name}. {payload.note or ''}"
                    task.updated_at = now
                    await log_activity(
                        db, task.id, "merged",
                        f"Task merged into primary task by {reviewer_name}. Reason: {mr.reason}",
                        reviewer.id,
                    )

        # Log on primary task
        await log_activity(
            db, mr.primary_task_id, "merge_approved",
            f"Merge request approved by {reviewer_name}. Duplicate tasks closed.",
            reviewer.id,
        )

        # Notify developer
        await notify(
            db, mr.requested_by,
            "Merge Request Approved",
            f"{reviewer_name} approved your merge request. Focus on the primary task.",
            mr.primary_task_id,
        )

    else:  # reject
        mr.status = "rejected"
        group.status = "rejected"
        group.updated_at = now

        for member in group.members:
            await log_activity(
                db, member.task_id, "merge_rejected",
                f"Merge request rejected by {reviewer_name}. {payload.note or ''}",
                reviewer.id,
            )

        await notify(
            db, mr.requested_by,
            "Merge Request Rejected",
            f"{reviewer_name} rejected your merge request. Please continue working on all tasks."
            + (f"\nNote: {payload.note}" if payload.note else ""),
            mr.primary_task_id,
        )

    await db.commit()
    await db.refresh(mr)

    return MergeRequestResponse(
        id=mr.id,
        group_id=mr.group_id,
        requested_by=mr.requested_by,
        requester_name=await _emp_name(db, mr.requested_by),
        primary_task_id=mr.primary_task_id,
        reason=mr.reason,
        status=mr.status,
        reviewed_by=mr.reviewed_by,
        reviewer_name=reviewer_name,
        review_note=mr.review_note,
        created_at=mr.created_at,
        reviewed_at=mr.reviewed_at,
    )


async def get_pending_merge_requests(
    db: AsyncSession,
    manager: Employee,
) -> list[MergeRequestResponse]:
    """Manager sees all pending merge requests for their org."""
    result = await db.execute(
        select(TrackerMergeRequest)
        .join(TrackerDuplicateGroup, TrackerDuplicateGroup.id == TrackerMergeRequest.group_id)
        .where(
            TrackerDuplicateGroup.organization_id == manager.organization_id,
            TrackerMergeRequest.status == "pending",
        )
        .order_by(TrackerMergeRequest.created_at.desc())
    )
    requests = result.scalars().all()
    responses = []
    for mr in requests:
        responses.append(MergeRequestResponse(
            id=mr.id,
            group_id=mr.group_id,
            requested_by=mr.requested_by,
            requester_name=await _emp_name(db, mr.requested_by),
            primary_task_id=mr.primary_task_id,
            reason=mr.reason,
            status=mr.status,
            reviewed_by=mr.reviewed_by,
            reviewer_name=await _emp_name(db, mr.reviewed_by),
            review_note=mr.review_note,
            created_at=mr.created_at,
            reviewed_at=mr.reviewed_at,
        ))
    return responses
