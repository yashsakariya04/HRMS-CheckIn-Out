import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.subtask import TrackerSubtask
from app.models.tracker.task import TrackerTask
from app.schemas.tracker.subtask import SubtaskCreate, SubtaskToggle
from app.services.tracker.activity_service import log_activity


async def add_subtask(
    db: AsyncSession,
    task_id: uuid.UUID,
    payload: SubtaskCreate,
    user: Employee,
) -> TrackerSubtask:
    task = await _get_accessible_task(db, task_id, user)
    subtask = TrackerSubtask(
        task_id=task_id,
        title=payload.title,
        created_by=user.id,
    )
    db.add(subtask)
    await db.flush()
    await log_activity(db, task_id, "subtask_added",
                       f"{user.full_name or user.email} added subtask: {payload.title}", user.id)
    await db.commit()
    await db.refresh(subtask)
    return subtask


async def toggle_subtask(
    db: AsyncSession,
    task_id: uuid.UUID,
    subtask_id: uuid.UUID,
    payload: SubtaskToggle,
    user: Employee,
) -> TrackerSubtask:
    await _get_accessible_task(db, task_id, user)
    result = await db.execute(
        select(TrackerSubtask).where(
            TrackerSubtask.id == subtask_id,
            TrackerSubtask.task_id == task_id,
        )
    )
    subtask = result.scalars().first()
    if not subtask:
        raise HTTPException(404, "Subtask not found")

    subtask.is_done = payload.is_done
    await log_activity(
        db, task_id, "subtask_toggled",
        f"{user.full_name or user.email} marked subtask '{subtask.title}' as {'done' if payload.is_done else 'undone'}",
        user.id,
    )
    await db.commit()
    await db.refresh(subtask)
    return subtask


async def delete_subtask(
    db: AsyncSession,
    task_id: uuid.UUID,
    subtask_id: uuid.UUID,
    user: Employee,
) -> None:
    await _get_accessible_task(db, task_id, user)
    result = await db.execute(
        select(TrackerSubtask).where(
            TrackerSubtask.id == subtask_id,
            TrackerSubtask.task_id == task_id,
        )
    )
    subtask = result.scalars().first()
    if not subtask:
        raise HTTPException(404, "Subtask not found")
    await db.delete(subtask)
    await db.commit()


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_accessible_task(
    db: AsyncSession, task_id: uuid.UUID, user: Employee
) -> TrackerTask:
    result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == task_id,
            TrackerTask.organization_id == user.organization_id,
        )
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(404, "Task not found")
    if user.role == "employee" and task.assigned_to != user.id and task.created_by != user.id:
        raise HTTPException(403, "Access denied")
    return task
