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
    # Only admin and superadmin can post comments
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(403, "Only admins can add comments. Employees use the task description.")

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

    # Notify assignee of admin comment
    if task.assigned_to:
        await notify(
            db, task.assigned_to,
            "New Comment from Admin",
            f"Admin commented on your task: {task.title}",
            task_id,
        )

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
