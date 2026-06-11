import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.subtask import TrackerChecklist, TrackerSubtask
from app.models.tracker.task import TrackerTask, TrackerTaskMember
from app.schemas.tracker.subtask import ChecklistCreate, ChecklistRename, SubtaskCreate, SubtaskToggle
from app.services.tracker.activity_service import log_activity


# ── Checklists ────────────────────────────────────────────────────────────────

async def create_checklist(
    db: AsyncSession,
    task_id: uuid.UUID,
    payload: ChecklistCreate,
    user: Employee,
) -> TrackerChecklist:
    await _get_accessible_task(db, task_id, user)
    checklist = TrackerChecklist(task_id=task_id, name=payload.name, created_by=user.id)
    db.add(checklist)
    await db.flush()
    await log_activity(db, task_id, "checklist_added",
                       f"{user.full_name or user.email} added checklist: {payload.name}", user.id)
    await db.commit()
    await db.refresh(checklist)
    return checklist


async def rename_checklist(
    db: AsyncSession,
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    payload: ChecklistRename,
    user: Employee,
) -> TrackerChecklist:
    checklist = await _get_checklist(db, task_id, checklist_id)
    checklist.name = payload.name
    await log_activity(db, task_id, "checklist_renamed",
                       f"{user.full_name or user.email} renamed checklist to: {payload.name}", user.id)
    await db.commit()
    await db.refresh(checklist)
    return checklist


async def delete_checklist(
    db: AsyncSession,
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    user: Employee,
) -> None:
    await _get_accessible_task(db, task_id, user)
    checklist = await _get_checklist(db, task_id, checklist_id)
    await db.delete(checklist)
    await db.commit()


async def list_checklists(
    db: AsyncSession,
    task_id: uuid.UUID,
    user: Employee,
) -> list[TrackerChecklist]:
    await _get_accessible_task(db, task_id, user)
    result = await db.execute(
        select(TrackerChecklist)
        .where(TrackerChecklist.task_id == task_id)
        .order_by(TrackerChecklist.created_at.asc())
    )
    return result.scalars().all()


# ── Subtask items ─────────────────────────────────────────────────────────────

async def add_subtask(
    db: AsyncSession,
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    payload: SubtaskCreate,
    user: Employee,
) -> TrackerSubtask:
    await _get_accessible_task(db, task_id, user)
    checklist = await _get_checklist(db, task_id, checklist_id)
    subtask = TrackerSubtask(checklist_id=checklist.id, title=payload.title, created_by=user.id)
    db.add(subtask)
    await db.flush()
    await log_activity(db, task_id, "subtask_added",
                       f"{user.full_name or user.email} added item '{payload.title}' to checklist '{checklist.name}'",
                       user.id)
    await db.commit()
    await db.refresh(subtask)
    return subtask


async def toggle_subtask(
    db: AsyncSession,
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    subtask_id: uuid.UUID,
    payload: SubtaskToggle,
    user: Employee,
) -> TrackerSubtask:
    await _get_accessible_task(db, task_id, user)
    subtask = await _get_subtask(db, checklist_id, subtask_id)
    subtask.is_done = payload.is_done
    await log_activity(
        db, task_id, "subtask_toggled",
        f"{user.full_name or user.email} marked '{subtask.title}' as {'done' if payload.is_done else 'undone'}",
        user.id,
    )
    await db.commit()
    await db.refresh(subtask)
    return subtask


async def delete_subtask(
    db: AsyncSession,
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    subtask_id: uuid.UUID,
    user: Employee,
) -> None:
    await _get_accessible_task(db, task_id, user)
    subtask = await _get_subtask(db, checklist_id, subtask_id)
    await db.delete(subtask)
    await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    if user.role == "employee":
        member_result = await db.execute(
            select(TrackerTaskMember).where(
                TrackerTaskMember.task_id == task_id,
                TrackerTaskMember.employee_id == user.id,
            )
        )
        is_member = member_result.scalars().first() is not None
        if not is_member and task.created_by != user.id:
            raise HTTPException(403, "Access denied")
    return task


async def _get_checklist(
    db: AsyncSession, task_id: uuid.UUID, checklist_id: uuid.UUID
) -> TrackerChecklist:
    result = await db.execute(
        select(TrackerChecklist).where(
            TrackerChecklist.id == checklist_id,
            TrackerChecklist.task_id == task_id,
        )
    )
    checklist = result.scalars().first()
    if not checklist:
        raise HTTPException(404, "Checklist not found")
    return checklist


async def _get_subtask(
    db: AsyncSession, checklist_id: uuid.UUID, subtask_id: uuid.UUID
) -> TrackerSubtask:
    result = await db.execute(
        select(TrackerSubtask).where(
            TrackerSubtask.id == subtask_id,
            TrackerSubtask.checklist_id == checklist_id,
        )
    )
    subtask = result.scalars().first()
    if not subtask:
        raise HTTPException(404, "Subtask item not found")
    return subtask
