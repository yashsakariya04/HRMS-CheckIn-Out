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
    BugReportCreate, EmployeeTaskCreate, AdminTaskCreate,
    TaskAssign, TaskStatusUpdate, TaskResponse, TaskFullDetail,
)
from app.services.tracker import task_service

router = APIRouter(prefix="/tracker/tasks", tags=["Tracker — Tasks"])


@router.post("/bug", response_model=TaskResponse, status_code=201)
async def create_bug_report(
    payload: BugReportCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee submits a bug report. Files uploaded separately via /attachments."""
    return await task_service.create_bug_report(db, payload, user)


@router.post("/self", response_model=TaskResponse, status_code=201)
async def create_self_task(
    payload: EmployeeTaskCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee creates and self-assigns a task — goes directly to todo, no admin approval."""
    return await task_service.create_self_assigned_task(db, payload, user)


@router.post("/admin", response_model=TaskResponse, status_code=201)
async def admin_create_task(
    payload: AdminTaskCreate,
    admin: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin creates a custom task and directly assigns it to an employee."""
    return await task_service.create_and_assign_task(db, payload, admin)


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
    """Returns full task detail including subtasks, comments, attachments, and timeline."""
    return await task_service.get_task_full_detail(db, task_id, user.organization_id)


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


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_status(
    task_id: uuid.UUID,
    payload: TaskStatusUpdate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.update_status(db, task_id, payload, user)
