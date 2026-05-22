import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.tracker.subtask import SubtaskCreate, SubtaskToggle, SubtaskResponse
from app.services.tracker import subtask_service

router = APIRouter(prefix="/tracker/tasks/{task_id}/subtasks", tags=["Tracker — Subtasks"])


@router.post("", response_model=SubtaskResponse, status_code=201)
async def add_subtask(
    task_id: uuid.UUID,
    payload: SubtaskCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await subtask_service.add_subtask(db, task_id, payload, user)


@router.patch("/{subtask_id}", response_model=SubtaskResponse)
async def toggle_subtask(
    task_id: uuid.UUID,
    subtask_id: uuid.UUID,
    payload: SubtaskToggle,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await subtask_service.toggle_subtask(db, task_id, subtask_id, payload, user)


@router.delete("/{subtask_id}", status_code=204)
async def delete_subtask(
    task_id: uuid.UUID,
    subtask_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await subtask_service.delete_subtask(db, task_id, subtask_id, user)
