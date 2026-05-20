"""
Core task service — create, assign, status transitions, filters.
All business rules and workflow enforcement live here.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.task import TrackerTask
from app.schemas.tracker.task import BugReportCreate, AdminTaskCreate, TaskAssign, TaskStatusUpdate
from app.services.tracker.activity_service import log_activity
from app.services.tracker.notification_service import notify

# Valid forward/backward transitions per role
_TRANSITIONS: dict[str, list[str]] = {
    "pending_approval": ["assigned", "rejected"],
    "assigned":         ["todo", "rejected"],
    "todo":             ["in_progress"],
    "in_progress":      ["blocked", "testing"],
    "blocked":          ["in_progress"],
    "testing":          ["completed", "in_progress"],
    "completed":        [],
    "rejected":         [],
}

_STATUS_LABELS = {
    "pending_approval": "Pending Approval",
    "assigned":         "Assigned",
    "todo":             "To Do",
    "in_progress":      "In Progress",
    "blocked":          "Blocked",
    "testing":          "Testing",
    "completed":        "Completed",
    "rejected":         "Rejected",
}


async def create_bug_report(
    db: AsyncSession,
    payload: BugReportCreate,
    creator: Employee,
) -> TrackerTask:
    """Employee submits a bug report — goes to pending_approval."""
    task = TrackerTask(
        organization_id=creator.organization_id,
        title=payload.title,
        description=payload.description,
        request_type="bug",
        priority="medium",   # admin sets priority when assigning
        created_by=creator.id,
        status="pending_approval",
    )
    db.add(task)
    await db.flush()
    await log_activity(
        db, task.id, "bug_reported",
        f"Bug reported by {creator.full_name or creator.email}",
        creator.id,
    )
    # Notify admins of new bug report
    admins = await _get_org_admins(db, creator.organization_id)
    for admin in admins:
        await notify(
            db, admin.id,
            "New Bug Report",
            f"{creator.full_name or creator.email} submitted a bug: {payload.title}",
            task.id,
        )
    await db.commit()
    await db.refresh(task)
    return task


async def create_and_assign_task(
    db: AsyncSession,
    payload: AdminTaskCreate,
    admin: Employee,
) -> TrackerTask:
    """Admin creates a custom task and directly assigns it in one step."""
    result = await db.execute(
        select(Employee).where(
            Employee.id == payload.assigned_to,
            Employee.organization_id == admin.organization_id,
            Employee.is_active == True,
        )
    )
    assignee = result.scalars().first()
    if not assignee:
        raise HTTPException(404, "Assignee not found in your organization")

    task = TrackerTask(
        organization_id=admin.organization_id,
        title=payload.title,
        description=payload.description,
        request_type="task",
        priority=payload.priority,
        deadline=payload.deadline,
        assigned_to=payload.assigned_to,
        created_by=admin.id,
        status="assigned",
    )
    db.add(task)
    await db.flush()

    await log_activity(
        db, task.id, "task_created",
        f"Task created and assigned to {assignee.full_name or assignee.email} by {admin.full_name or admin.email}",
        admin.id,
    )

    # Persist admin comment if provided
    if payload.comment:
        from app.models.tracker.comment import TrackerComment
        comment = TrackerComment(
            task_id=task.id,
            user_id=admin.id,
            message=payload.comment,
        )
        db.add(comment)
        await db.flush()
        await log_activity(
            db, task.id, "comment_added",
            f"{admin.full_name or admin.email} added a comment",
            admin.id,
        )

    await notify(
        db, assignee.id,
        "New Task Assigned",
        f"You have been assigned: {task.title}",
        task.id,
    )
    await db.commit()
    await db.refresh(task)
    return task


async def assign_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    payload: TaskAssign,
    admin: Employee,
) -> TrackerTask:
    task = await _get_task(db, task_id, admin.organization_id)
    if task.status not in ("pending_approval", "assigned"):
        raise HTTPException(400, "Task can only be assigned from pending_approval or assigned state")

    # Verify assignee exists in same org
    result = await db.execute(
        select(Employee).where(
            Employee.id == payload.assigned_to,
            Employee.organization_id == admin.organization_id,
            Employee.is_active == True,
        )
    )
    assignee = result.scalars().first()
    if not assignee:
        raise HTTPException(404, "Assignee not found in your organization")

    task.assigned_to = payload.assigned_to
    task.priority = payload.priority
    task.deadline = payload.deadline
    task.status = "assigned"
    task.updated_at = datetime.now(timezone.utc)

    await log_activity(
        db, task.id, "task_assigned",
        f"Task assigned to {assignee.full_name or assignee.email} by {admin.full_name or admin.email}",
        admin.id,
    )

    # Persist admin comment on assignment if provided
    if payload.comment:
        from app.models.tracker.comment import TrackerComment
        comment = TrackerComment(
            task_id=task.id,
            user_id=admin.id,
            message=payload.comment,
        )
        db.add(comment)
        await db.flush()
        await log_activity(
            db, task.id, "comment_added",
            f"{admin.full_name or admin.email} added a comment on assignment",
            admin.id,
        )

    await notify(
        db, assignee.id,
        "New Task Assigned",
        f"You have been assigned: {task.title}",
        task.id,
    )
    await db.commit()
    await db.refresh(task)
    return task


async def update_status(
    db: AsyncSession,
    task_id: uuid.UUID,
    payload: TaskStatusUpdate,
    user: Employee,
) -> TrackerTask:
    task = await _get_task(db, task_id, user.organization_id)

    # Employees can only update their own assigned tasks
    if user.role == "employee" and task.assigned_to != user.id:
        raise HTTPException(403, "You can only update tasks assigned to you")

    allowed = _TRANSITIONS.get(task.status, [])
    if payload.status not in allowed:
        raise HTTPException(
            400,
            f"Cannot transition from '{task.status}' to '{payload.status}'. "
            f"Allowed: {allowed}",
        )

    # Blocked requires a reason
    if payload.status == "blocked" and not payload.blocked_reason:
        raise HTTPException(400, "blocked_reason is required when marking a task as blocked")

    old_status = task.status
    task.status = payload.status
    task.blocked_reason = payload.blocked_reason if payload.status == "blocked" else None
    task.updated_at = datetime.now(timezone.utc)

    detail = (
        f"Status changed from {_STATUS_LABELS[old_status]} to {_STATUS_LABELS[payload.status]}"
    )
    if payload.status == "blocked":
        detail += f" — Reason: {payload.blocked_reason}"

    await log_activity(db, task.id, "status_changed", detail, user.id)

    # Notify admin when task is blocked
    if payload.status == "blocked":
        admins = await _get_org_admins(db, user.organization_id)
        for admin in admins:
            await notify(
                db, admin.id,
                "Task Blocked",
                f"Task '{task.title}' was marked blocked: {payload.blocked_reason}",
                task.id,
            )

    # Notify assignee when admin changes status
    if user.role in ("admin", "superadmin") and task.assigned_to:
        await notify(
            db, task.assigned_to,
            "Task Status Updated",
            f"Your task '{task.title}' status changed to {_STATUS_LABELS[payload.status]}",
            task.id,
        )

    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    admin: Employee,
) -> None:
    task = await _get_task(db, task_id, admin.organization_id)
    await db.delete(task)
    await db.commit()


async def get_tasks_for_employee(
    db: AsyncSession,
    user: Employee,
    status: Optional[str] = None,
) -> list[TrackerTask]:
    ownership = or_(
        TrackerTask.assigned_to == user.id,
        TrackerTask.created_by == user.id,
    )
    conditions = [
        TrackerTask.organization_id == user.organization_id,
        ownership,
    ]
    if status:
        conditions.append(TrackerTask.status == status)
    result = await db.execute(
        select(TrackerTask).where(and_(*conditions)).order_by(TrackerTask.created_at.desc())
    )
    return result.scalars().all()


async def get_tasks_for_admin(
    db: AsyncSession,
    org_id: uuid.UUID,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[uuid.UUID] = None,
    overdue_only: bool = False,
) -> list[TrackerTask]:
    conditions = [TrackerTask.organization_id == org_id]
    if status:
        conditions.append(TrackerTask.status == status)
    if priority:
        conditions.append(TrackerTask.priority == priority)
    if assigned_to:
        conditions.append(TrackerTask.assigned_to == assigned_to)
    if overdue_only:
        now = datetime.now(timezone.utc)
        conditions.append(TrackerTask.deadline < now)
        conditions.append(TrackerTask.status.notin_(["completed", "rejected"]))

    result = await db.execute(
        select(TrackerTask).where(and_(*conditions)).order_by(TrackerTask.created_at.desc())
    )
    return result.scalars().all()


async def get_task_detail(
    db: AsyncSession,
    task_id: uuid.UUID,
    org_id: uuid.UUID,
) -> TrackerTask:
    return await _get_task(db, task_id, org_id)


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
