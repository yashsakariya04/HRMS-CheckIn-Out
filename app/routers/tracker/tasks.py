"""
Task router — CRUD, assignment, status transitions, timeline, filters.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.tracker.task import (
    TaskCreate, TaskAddMembers, TaskRemoveMembers, TaskAssign, TaskStatusUpdate, TaskDescriptionUpdate,
    TaskResponse, TaskFullDetail, TaskTimelineResponse, TaskDuplicateCheckRequest,
)
from app.services.tracker import task_service

router = APIRouter(prefix="/tracker/tasks", tags=["Tracker — Tasks"])


@router.post("/admin", response_model=TaskResponse, status_code=201)
async def create_task(
    payload: TaskCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a task. Works for both admin and employee.
    - assigned_to=[]  → self-assign, status=todo
    - assigned_to=[ids] → assign to others (any user can do this), status=assigned
    """
    return await task_service.create_task(db, payload, user)


@router.post("/check-duplicate", response_model=list[TaskResponse])
async def check_duplicate_task(
    payload: TaskDuplicateCheckRequest,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a draft task is highly similar to existing active tasks.
    A threshold of 0.15 roughly corresponds to 85% similarity.
    """
    return await task_service.check_duplicates(
        db,
        user.organization_id,
        payload.title,
        payload.description,
        payload.threshold,
    )


@router.post("/{task_id}/members", response_model=TaskResponse)
async def add_members(
    task_id: uuid.UUID,
    payload: TaskAddMembers,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add new members to an existing task."""
    return await task_service.add_task_members(db, task_id, payload, user)


@router.delete("/{task_id}/members", response_model=TaskResponse)
async def remove_members(
    task_id: uuid.UUID,
    payload: TaskRemoveMembers,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove members from a task. Any member, creator, or admin can do this."""
    return await task_service.remove_task_members(db, task_id, payload, user)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[uuid.UUID] = Query(None),
    overdue_only: bool = Query(False),
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role in ("admin", "superadmin"):
        return await task_service.get_tasks_for_admin(
            db, user.organization_id, status, priority, assigned_to, overdue_only
        )
    return await task_service.get_tasks_for_employee(db, user, status)


@router.get("/{task_id}", response_model=TaskFullDetail)
async def get_task(
    task_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.get_task_full_detail(db, task_id, user.organization_id)


@router.get("/{task_id}/timeline", response_model=TaskTimelineResponse)
async def get_task_timeline(
    task_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the activity timeline for a task separately."""
    return await task_service.get_task_timeline(db, task_id, user.organization_id)


@router.post("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: uuid.UUID,
    payload: TaskAssign,
    admin: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.assign_task(db, task_id, payload, admin)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    admin: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await task_service.delete_task(db, task_id, admin)


@router.patch("/{task_id}/description", response_model=TaskResponse)
async def update_description(
    task_id: uuid.UUID,
    payload: TaskDescriptionUpdate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.update_description(db, task_id, payload.description, user)


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_status(
    task_id: uuid.UUID,
    payload: TaskStatusUpdate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.update_status(db, task_id, payload, user)
