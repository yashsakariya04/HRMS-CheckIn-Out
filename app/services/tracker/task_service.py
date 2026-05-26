"""
Core task service — create, assign, status transitions, filters, full detail.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.activity_log import TrackerActivityLog
from app.models.tracker.attachment import TrackerAttachment
from app.models.tracker.comment import TrackerComment
from app.models.tracker.subtask import TrackerChecklist
from app.models.tracker.task import TrackerTask, TrackerTaskMember
from app.schemas.tracker.task import (
    TaskCreate, TaskAddMembers, TaskAssign, TaskStatusUpdate, TaskFullDetail,
    CommentInDetail, AttachmentInDetail, ActivityInDetail,
    ChecklistInDetail, ChecklistItemInDetail,
)
from app.services.tracker.activity_service import log_activity
from app.services.tracker.notification_service import notify

_KANBAN_STAGES = {"todo", "in_progress", "in_development", "in_qa", "in_stage", "in_production"}

_TRANSITIONS: dict[str, list[str]] = {
    "pending_approval": ["assigned", "rejected"],
    "assigned":         ["todo", "in_progress", "rejected"],
    "todo":             ["in_progress"],
    "in_progress":      ["todo", "in_development"],
    "in_development":   ["in_progress", "in_qa"],
    "in_qa":            ["in_development", "in_stage"],
    "in_stage":         ["in_qa", "in_production"],
    "in_production":    [],
    "rejected":         [],
}

_STATUS_LABELS = {
    "pending_approval": "Pending Approval",
    "assigned":         "Assigned",
    "todo":             "To Do",
    "in_progress":      "In Progress",
    "in_development":   "In Development",
    "in_qa":            "In QA",
    "in_stage":         "In Stage",
    "in_production":    "In Production",
    "rejected":         "Rejected",
}


def _task_to_response(task: TrackerTask) -> dict:
    """Convert ORM task to dict with assigned_to as list of UUIDs."""
    return {
        **{c: getattr(task, c) for c in (
            "id", "title", "description", "request_type", "priority",
            "status", "deadline", "blocked_reason", "created_by",
            "created_at", "updated_at",
        )},
        "assigned_to": [m.employee_id for m in task.members],
    }


async def create_task(
    db: AsyncSession,
    payload: TaskCreate,
    creator: Employee,
) -> dict:
    """
    Unified task creation for both admin and employee.

    Rules:
    - assigned_to=[]  → self-assign, status=todo, request_type=task
    - assigned_to=[ids] and creator is employee → assign to others, status=assigned, request_type=task
    - Bug reports are no longer a separate endpoint; use request_type via payload if needed.
      Here we always create request_type='task'. Bug reports remain via /bug if kept,
      but this endpoint handles all task creation.
    - Any user (admin or employee) can assign to anyone without approval.
    """
    assignees = payload.assigned_to or [creator.id]  # default: self

    # Validate all assignees belong to the same org
    result = await db.execute(
        select(Employee).where(
            Employee.id.in_(assignees),
            Employee.organization_id == creator.organization_id,
            Employee.is_active == True,
            Employee.role != "superadmin",
        )
    )
    found = result.scalars().all()
    if len(found) != len(set(assignees)):
        raise HTTPException(404, "One or more assignees not found in your organization")

    is_self_only = set(assignees) == {creator.id}
    status = "todo" if is_self_only else "assigned"

    task = TrackerTask(
        organization_id=creator.organization_id,
        title=payload.title,
        description=payload.description,
        request_type="task",
        priority=payload.priority,
        deadline=payload.deadline,
        created_by=creator.id,
        status=status,
    )
    db.add(task)
    await db.flush()

    for emp_id in set(assignees):
        db.add(TrackerTaskMember(task_id=task.id, employee_id=emp_id))
    await db.flush()

    names = ", ".join(e.full_name or e.email for e in found)
    await log_activity(
        db, task.id, "task_created",
        f"Task created by {creator.full_name or creator.email}, assigned to: {names}",
        creator.id,
    )

    if payload.comment:
        db.add(TrackerComment(task_id=task.id, user_id=creator.id, message=payload.comment))
        await db.flush()
        await log_activity(db, task.id, "comment_added",
                           f"{creator.full_name or creator.email} added a comment", creator.id)

    for emp in found:
        if emp.id != creator.id:
            await notify(db, emp.id, "New Task Assigned",
                         f"You have been assigned: {task.title}", task.id)

    await db.commit()
    await db.refresh(task)
    return _task_to_response(task)


async def add_task_members(
    db: AsyncSession,
    task_id: uuid.UUID,
    payload: TaskAddMembers,
    actor: Employee,
) -> dict:
    """Add new members to an existing task."""
    task = await _get_task(db, task_id, actor.organization_id)

    # Validate new members
    result = await db.execute(
        select(Employee).where(
            Employee.id.in_(payload.employee_ids),
            Employee.organization_id == actor.organization_id,
            Employee.is_active == True,
            Employee.role != "superadmin",
        )
    )
    found = result.scalars().all()
    if len(found) != len(set(payload.employee_ids)):
        raise HTTPException(404, "One or more employees not found in your organization")

    existing_ids = {m.employee_id for m in task.members}
    new_members = [e for e in found if e.id not in existing_ids]

    if not new_members:
        raise HTTPException(400, "All specified employees are already members of this task")

    for emp in new_members:
        db.add(TrackerTaskMember(task_id=task.id, employee_id=emp.id))
    await db.flush()

    names = ", ".join(e.full_name or e.email for e in new_members)
    await log_activity(
        db, task.id, "members_added",
        f"{actor.full_name or actor.email} added members: {names}",
        actor.id,
    )
    for emp in new_members:
        await notify(db, emp.id, "Added to Task",
                     f"You have been added to task: {task.title}", task.id)

    await db.commit()
    await db.refresh(task)
    return _task_to_response(task)


async def assign_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    payload: TaskAssign,
    admin: Employee,
) -> dict:
    """Replace all current assignees on a pending/assigned task."""
    task = await _get_task(db, task_id, admin.organization_id)
    if task.status not in ("pending_approval", "assigned"):
        raise HTTPException(400, "Task can only be reassigned from pending_approval or assigned state")

    result = await db.execute(
        select(Employee).where(
            Employee.id.in_(payload.assigned_to),
            Employee.organization_id == admin.organization_id,
            Employee.is_active == True,
            Employee.role != "superadmin",
        )
    )
    found = result.scalars().all()
    if len(found) != len(set(payload.assigned_to)):
        raise HTTPException(404, "One or more assignees not found in your organization")

    # Replace members
    await db.execute(delete(TrackerTaskMember).where(TrackerTaskMember.task_id == task.id))
    for emp_id in set(payload.assigned_to):
        db.add(TrackerTaskMember(task_id=task.id, employee_id=emp_id))
    await db.flush()

    task.priority = payload.priority
    task.deadline = payload.deadline
    task.status = "assigned"
    task.updated_at = datetime.now(timezone.utc)

    names = ", ".join(e.full_name or e.email for e in found)
    await log_activity(
        db, task.id, "task_assigned",
        f"Task assigned to {names} by {admin.full_name or admin.email}",
        admin.id,
    )

    if payload.comment:
        db.add(TrackerComment(task_id=task.id, user_id=admin.id, message=payload.comment))
        await db.flush()
        await log_activity(db, task.id, "comment_added",
                           f"{admin.full_name or admin.email} added a comment on assignment", admin.id)

    for emp in found:
        await notify(db, emp.id, "New Task Assigned",
                     f"You have been assigned: {task.title}", task.id)

    await db.commit()
    await db.refresh(task)
    return _task_to_response(task)


async def update_status(
    db: AsyncSession,
    task_id: uuid.UUID,
    payload: TaskStatusUpdate,
    user: Employee,
) -> dict:
    task = await _get_task(db, task_id, user.organization_id)

    member_ids = {m.employee_id for m in task.members}
    if user.role == "employee" and user.id not in member_ids and task.created_by != user.id:
        raise HTTPException(403, "You can only update tasks you are a member of or created")

    allowed = _TRANSITIONS.get(task.status, [])
    if payload.status not in allowed:
        raise HTTPException(
            400,
            f"Cannot transition from '{task.status}' to '{payload.status}'. Allowed: {allowed}",
        )

    old_status = task.status
    task.status = payload.status
    task.blocked_reason = None
    task.updated_at = datetime.now(timezone.utc)

    await log_activity(
        db, task.id, "status_changed",
        f"Status changed from {_STATUS_LABELS[old_status]} to {_STATUS_LABELS[payload.status]}",
        user.id,
    )

    if user.role in ("admin", "superadmin"):
        for mid in member_ids:
            await notify(
                db, mid,
                "Task Status Updated",
                f"Task '{task.title}' status changed to {_STATUS_LABELS[payload.status]}",
                task.id,
            )

    await db.commit()
    await db.refresh(task)
    return _task_to_response(task)


async def delete_task(db: AsyncSession, task_id: uuid.UUID, admin: Employee) -> None:
    task = await _get_task(db, task_id, admin.organization_id)
    await db.delete(task)
    await db.commit()


async def get_tasks_for_employee(
    db: AsyncSession,
    user: Employee,
    status: Optional[str] = None,
) -> list[dict]:
    # Tasks where user is a member OR creator
    member_task_ids_result = await db.execute(
        select(TrackerTaskMember.task_id).where(TrackerTaskMember.employee_id == user.id)
    )
    member_task_ids = {r for r in member_task_ids_result.scalars().all()}

    conditions = [
        TrackerTask.organization_id == user.organization_id,
        or_(TrackerTask.id.in_(member_task_ids), TrackerTask.created_by == user.id),
    ]
    if status:
        conditions.append(TrackerTask.status == status)

    result = await db.execute(
        select(TrackerTask).where(and_(*conditions)).order_by(TrackerTask.created_at.desc())
    )
    return [_task_to_response(t) for t in result.scalars().all()]


async def get_tasks_for_admin(
    db: AsyncSession,
    org_id: uuid.UUID,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[uuid.UUID] = None,
    overdue_only: bool = False,
) -> list[dict]:
    conditions = [TrackerTask.organization_id == org_id]
    if status:
        conditions.append(TrackerTask.status == status)
    if priority:
        conditions.append(TrackerTask.priority == priority)
    if assigned_to:
        member_ids_result = await db.execute(
            select(TrackerTaskMember.task_id).where(TrackerTaskMember.employee_id == assigned_to)
        )
        task_ids = member_ids_result.scalars().all()
        conditions.append(TrackerTask.id.in_(task_ids))
    if overdue_only:
        now = datetime.now(timezone.utc)
        conditions.append(TrackerTask.deadline < now)
        conditions.append(TrackerTask.status.notin_(["in_production", "rejected"]))

    result = await db.execute(
        select(TrackerTask).where(and_(*conditions)).order_by(TrackerTask.created_at.desc())
    )
    return [_task_to_response(t) for t in result.scalars().all()]


async def get_task_full_detail(
    db: AsyncSession,
    task_id: uuid.UUID,
    org_id: uuid.UUID,
) -> TaskFullDetail:
    task = await _get_task(db, task_id, org_id)

    member_ids = [m.employee_id for m in task.members]
    assignee_names = [n for n in [await _get_employee_name(db, mid) for mid in member_ids] if n]
    creator_name = await _get_employee_name(db, task.created_by)

    cl_result = await db.execute(
        select(TrackerChecklist).where(TrackerChecklist.task_id == task_id).order_by(TrackerChecklist.created_at.asc())
    )
    checklists = [
        ChecklistInDetail(
            id=cl.id, name=cl.name, created_by=cl.created_by, created_at=cl.created_at,
            items=[
                ChecklistItemInDetail(id=i.id, title=i.title, is_done=i.is_done,
                                      created_by=i.created_by, created_at=i.created_at)
                for i in cl.items
            ],
        )
        for cl in cl_result.scalars().all()
    ]

    com_result = await db.execute(
        select(TrackerComment).where(TrackerComment.task_id == task_id).order_by(TrackerComment.created_at.asc())
    )
    comments = []
    for c in com_result.scalars().all():
        name = await _get_employee_name(db, c.user_id)
        comments.append(CommentInDetail(id=c.id, user_id=c.user_id, author_name=name,
                                        message=c.message, created_at=c.created_at))

    att_result = await db.execute(
        select(TrackerAttachment).where(TrackerAttachment.task_id == task_id).order_by(TrackerAttachment.created_at.asc())
    )
    attachments = [
        AttachmentInDetail(id=a.id, file_url=a.file_url, original_filename=a.original_filename,
                           file_type=a.file_type, file_size_bytes=a.file_size_bytes,
                           uploaded_by=a.uploaded_by, created_at=a.created_at)
        for a in att_result.scalars().all()
    ]

    tl_result = await db.execute(
        select(TrackerActivityLog).where(TrackerActivityLog.task_id == task_id).order_by(TrackerActivityLog.created_at.asc())
    )
    timeline = []
    for log in tl_result.scalars().all():
        name = await _get_employee_name(db, log.performed_by) if log.performed_by else None
        timeline.append(ActivityInDetail(id=log.id, action=log.action, detail=log.detail,
                                         performed_by=log.performed_by, performer_name=name,
                                         created_at=log.created_at))

    return TaskFullDetail(
        id=task.id,
        title=task.title,
        description=task.description,
        request_type=task.request_type,
        priority=task.priority,
        status=task.status,
        deadline=task.deadline,
        blocked_reason=task.blocked_reason,
        assigned_to=member_ids,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        assignee_names=assignee_names,
        creator_name=creator_name,
        checklists=checklists,
        comments=comments,
        attachments=attachments,
        timeline=timeline,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_task(db: AsyncSession, task_id: uuid.UUID, org_id: uuid.UUID) -> TrackerTask:
    result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == task_id,
            TrackerTask.organization_id == org_id,
        )
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(404, "Task not found")
    return task


async def _get_org_admins(db: AsyncSession, org_id: uuid.UUID) -> list[Employee]:
    result = await db.execute(
        select(Employee).where(
            Employee.organization_id == org_id,
            Employee.role.in_(["admin", "superadmin"]),
            Employee.is_active == True,
        )
    )
    return result.scalars().all()


async def _get_employee_name(db: AsyncSession, emp_id: uuid.UUID | None) -> str | None:
    if not emp_id:
        return None
    result = await db.execute(select(Employee).where(Employee.id == emp_id))
    emp = result.scalars().first()
    return (emp.full_name or emp.email) if emp else None
