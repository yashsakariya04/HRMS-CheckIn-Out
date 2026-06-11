"""
Comment service — add and fetch comments, write activity log entry.
"""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.comment import TrackerComment
from app.models.tracker.task import TrackerTask
from app.schemas.tracker.comment import CommentCreate
from app.services.tracker.activity_service import log_activity
from app.services.tracker.notification_service import notify


async def add_comment(
    db: AsyncSession,
    task_id: uuid.UUID,
    payload: CommentCreate,
    user: Employee,
) -> TrackerComment:
    # Verify task exists in same org
    result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == task_id,
            TrackerTask.organization_id == user.organization_id,
        )
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(404, "Task not found")

    # Employees can only comment on tasks they are assigned to or created
    member_ids = {m.employee_id for m in task.members}
    if user.role == "employee" and user.id not in member_ids and task.created_by != user.id:
        raise HTTPException(403, "You can only comment on tasks assigned to or created by you")

    comment = TrackerComment(
        task_id=task_id,
        user_id=user.id,
        message=payload.message,
    )
    db.add(comment)
    await db.flush()

    await log_activity(
        db, task_id, "comment_added",
        f"{user.full_name or user.email} added a comment",
        user.id,
    )

    # Notify the other party
    if user.role in ("admin", "superadmin") and task.members:
        for m in task.members:
            await notify(db, m.employee_id, "New Comment",
                         f"Admin commented on your task: {task.title}", task_id)
    elif user.role == "employee":
        admins_result = await db.execute(
            select(Employee).where(
                Employee.organization_id == user.organization_id,
                Employee.role.in_(["admin", "superadmin"]),
                Employee.is_active == True,
            )
        )
        for admin in admins_result.scalars().all():
            await notify(db, admin.id, "New Comment from Employee",
                         f"{user.full_name or user.email} commented on task: {task.title}", task_id)

    await db.commit()
    await db.refresh(comment)
    return comment


async def get_comments(
    db: AsyncSession,
    task_id: uuid.UUID,
    org_id: uuid.UUID,
) -> list[TrackerComment]:
    # Verify task belongs to org
    result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == task_id,
            TrackerTask.organization_id == org_id,
        )
    )
    if not result.scalars().first():
        raise HTTPException(404, "Task not found")

    result = await db.execute(
        select(TrackerComment)
        .where(TrackerComment.task_id == task_id)
        .order_by(TrackerComment.created_at.asc())
    )
    return result.scalars().all()
