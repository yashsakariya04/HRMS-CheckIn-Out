"""
Core task service — create, assign, status transitions, filters, full detail.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.activity_log import TrackerActivityLog
from app.models.tracker.attachment import TrackerAttachment
from app.models.tracker.comment import TrackerComment
from app.models.tracker.subtask import TrackerSubtask
from app.models.tracker.task import TrackerTask
from app.schemas.tracker.task import (
    AdminTaskCreate, BugReportCreate, EmployeeTaskCreate,
    TaskAssign, TaskStatusUpdate, TaskFullDetail,
    CommentInDetail, AttachmentInDetail, ActivityInDetail, SubtaskInDetail,
)
from app.services.tracker.activity_service import log_activity
from app.services.tracker.notification_service import notify

# Kanban stages — free movement between any of these
_KANBAN_STAGES = {"todo", "in_progress", "in_development", "in_qa", "in_stage", "in_production"}

_TRANSITIONS: dict[str, list[str]] = {
    "pending_approval": ["assigned", "rejected"],
    "assigned":         ["todo", "rejected"],
    # Free movement within kanban — in_production is terminal
    "todo":             ["in_progress", "in_development", "in_qa", "in_stage", "in_production"],
    "in_progress":      ["todo", "in_development", "in_qa", "in_stage", "in_production"],
    "in_development":   ["todo", "in_progress", "in_qa", "in_stage", "in_production"],
    "in_qa":            ["todo", "in_progress", "in_development", "in_stage", "in_production"],
    "in_stage":         ["todo", "in_progress", "in_development", "in_qa", "in_production"],
    "in_production":    [],  # terminal
    "rejected":         [],  # terminal
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
        priority="medium",
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


async def create_self_assigned_task(
    db: AsyncSession,
    payload: EmployeeTaskCreate,
    creator: Employee,
) -> TrackerTask:
    """Employee creates and self-assigns a task — goes directly to todo, no admin approval."""
    task = TrackerTask(
        organization_id=creator.organization_id,
        title=payload.title,
        description=payload.description,
        request_type="task",
        priority=payload.priority,
        deadline=payload.deadline,
        assigned_to=creator.id,
        created_by=creator.id,
        status="todo",
    )
    db.add(task)
    await db.flush()
    await log_activity(
        db, task.id, "task_created",
        f"Task self-assigned by {creator.full_name or creator.email}",
        creator.id,
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
            Employee.role != "superadmin",
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

    if payload.comment:
        from app.models.tracker.comment import TrackerComment
        db.add(TrackerComment(task_id=task.id, user_id=admin.id, message=payload.comment))
        await db.flush()
        await log_activity(db, task.id, "comment_added",
                           f"{admin.full_name or admin.email} added a comment", admin.id)

    await notify(db, assignee.id, "New Task Assigned",
                 f"You have been assigned: {task.title}", task.id)
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

    result = await db.execute(
        select(Employee).where(
            Employee.id == payload.assigned_to,
            Employee.organization_id == admin.organization_id,
            Employee.is_active == True,
            Employee.role != "superadmin",
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

    if payload.comment:
        from app.models.tracker.comment import TrackerComment
        db.add(TrackerComment(task_id=task.id, user_id=admin.id, message=payload.comment))
        await db.flush()
        await log_activity(db, task.id, "comment_added",
                           f"{admin.full_name or admin.email} added a comment on assignment", admin.id)

    await notify(db, assignee.id, "New Task Assigned",
                 f"You have been assigned: {task.title}", task.id)
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

    if user.role == "employee" and task.assigned_to != user.id and task.created_by != user.id:
        raise HTTPException(403, "You can only update tasks assigned to or created by you")

    allowed = _TRANSITIONS.get(task.status, [])
    if payload.status not in allowed:
        raise HTTPException(
            400,
            f"Cannot transition from '{task.status}' to '{payload.status}'. Allowed: {allowed}",
        )

    old_status = task.status
    task.status = payload.status
    task.blocked_reason = None  # removed blocked concept
    task.updated_at = datetime.now(timezone.utc)

    await log_activity(
        db, task.id, "status_changed",
        f"Status changed from {_STATUS_LABELS[old_status]} to {_STATUS_LABELS[payload.status]}",
        user.id,
    )

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


async def delete_task(db: AsyncSession, task_id: uuid.UUID, admin: Employee) -> None:
    task = await _get_task(db, task_id, admin.organization_id)
    await db.delete(task)
    await db.commit()


async def get_tasks_for_employee(
    db: AsyncSession,
    user: Employee,
    status: Optional[str] = None,
) -> list[TrackerTask]:
    conditions = [
        TrackerTask.organization_id == user.organization_id,
        or_(TrackerTask.assigned_to == user.id, TrackerTask.created_by == user.id),
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
        conditions.append(TrackerTask.status.notin_(["in_production", "rejected"]))

    result = await db.execute(
        select(TrackerTask).where(and_(*conditions)).order_by(TrackerTask.created_at.desc())
    )
    return result.scalars().all()


async def get_task_full_detail(
    db: AsyncSession,
    task_id: uuid.UUID,
    org_id: uuid.UUID,
) -> TaskFullDetail:
    """Return a task with all related data: subtasks, comments, attachments, timeline."""
    task = await _get_task(db, task_id, org_id)

    # Resolve names
    assignee_name = await _get_employee_name(db, task.assigned_to)
    creator_name  = await _get_employee_name(db, task.created_by)

    # Subtasks
    sub_result = await db.execute(
        select(TrackerSubtask)
        .where(TrackerSubtask.task_id == task_id)
        .order_by(TrackerSubtask.created_at.asc())
    )
    subtasks = [
        SubtaskInDetail(
            id=s.id, title=s.title, is_done=s.is_done,
            created_by=s.created_by, created_at=s.created_at,
        )
        for s in sub_result.scalars().all()
    ]

    # Comments
    com_result = await db.execute(
        select(TrackerComment)
        .where(TrackerComment.task_id == task_id)
        .order_by(TrackerComment.created_at.asc())
    )
    comments = []
    for c in com_result.scalars().all():
        name = await _get_employee_name(db, c.user_id)
        comments.append(CommentInDetail(
            id=c.id, user_id=c.user_id, author_name=name,
            message=c.message, created_at=c.created_at,
        ))

    # Attachments
    att_result = await db.execute(
        select(TrackerAttachment)
        .where(TrackerAttachment.task_id == task_id)
        .order_by(TrackerAttachment.created_at.asc())
    )
    attachments = [
        AttachmentInDetail(
            id=a.id, file_url=a.file_url, original_filename=a.original_filename,
            file_type=a.file_type, file_size_bytes=a.file_size_bytes,
            uploaded_by=a.uploaded_by, created_at=a.created_at,
        )
        for a in att_result.scalars().all()
    ]

    # Timeline
    tl_result = await db.execute(
        select(TrackerActivityLog)
        .where(TrackerActivityLog.task_id == task_id)
        .order_by(TrackerActivityLog.created_at.asc())
    )
    timeline = []
    for log in tl_result.scalars().all():
        name = await _get_employee_name(db, log.performed_by) if log.performed_by else None
        timeline.append(ActivityInDetail(
            id=log.id, action=log.action, detail=log.detail,
            performed_by=log.performed_by, performer_name=name,
            created_at=log.created_at,
        ))

    return TaskFullDetail(
        id=task.id,
        title=task.title,
        description=task.description,
        request_type=task.request_type,
        priority=task.priority,
        status=task.status,
        deadline=task.deadline,
        blocked_reason=task.blocked_reason,
        assigned_to=task.assigned_to,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        assignee_name=assignee_name,
        creator_name=creator_name,
        subtasks=subtasks,
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
