import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.tracker.subtask import (
    ChecklistCreate, ChecklistRename, ChecklistResponse,
    SubtaskCreate, SubtaskToggle, SubtaskItemResponse,
)
from app.services.tracker import subtask_service

router = APIRouter(prefix="/tracker/tasks/{task_id}", tags=["Tracker — Checklists"])


# ── Checklists ────────────────────────────────────────────────────────────────

@router.get("/checklists", response_model=list[ChecklistResponse])
async def list_checklists(
    task_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await subtask_service.list_checklists(db, task_id, user)


@router.post("/checklists", response_model=ChecklistResponse, status_code=201)
async def create_checklist(
    task_id: uuid.UUID,
    payload: ChecklistCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await subtask_service.create_checklist(db, task_id, payload, user)


@router.patch("/checklists/{checklist_id}", response_model=ChecklistResponse)
async def rename_checklist(
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    payload: ChecklistRename,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await subtask_service.rename_checklist(db, task_id, checklist_id, payload, user)


@router.delete("/checklists/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist(
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await subtask_service.delete_checklist(db, task_id, checklist_id, user)


# ── Subtask items ─────────────────────────────────────────────────────────────

@router.post("/checklists/{checklist_id}/items", response_model=SubtaskItemResponse, status_code=201)
async def add_subtask(
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    payload: SubtaskCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await subtask_service.add_subtask(db, task_id, checklist_id, payload, user)


@router.patch("/checklists/{checklist_id}/items/{subtask_id}", response_model=SubtaskItemResponse)
async def toggle_subtask(
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    subtask_id: uuid.UUID,
    payload: SubtaskToggle,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await subtask_service.toggle_subtask(db, task_id, checklist_id, subtask_id, payload, user)


@router.delete("/checklists/{checklist_id}/items/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subtask(
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    subtask_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await subtask_service.delete_subtask(db, task_id, checklist_id, subtask_id, user)
