"""
Task router — CRUD, assignment, status transitions, timeline, filters.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.models.tracker.activity_log import TrackerActivityLog
from app.schemas.tracker.task import BugReportCreate, AdminTaskCreate, TaskAssign, TaskStatusUpdate, TaskResponse
from app.schemas.tracker.common import ActivityLogResponse
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


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.get_task_detail(db, task_id, user.organization_id)


@router.post("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: uuid.UUID,
    payload: TaskAssign,
    admin: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.assign_task(db, task_id, payload, admin)


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_status(
    task_id: uuid.UUID,
    payload: TaskStatusUpdate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.update_status(db, task_id, payload, user)


@router.get("/{task_id}/timeline", response_model=list[ActivityLogResponse])
async def get_timeline(
    task_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify access
    task = await task_service.get_task_detail(db, task_id, user.organization_id)
    if user.role == "employee" and task.assigned_to != user.id and task.created_by != user.id:
        from fastapi import HTTPException
        raise HTTPException(403, "Access denied")

    result = await db.execute(
        select(TrackerActivityLog)
        .where(TrackerActivityLog.task_id == task_id)
        .order_by(TrackerActivityLog.created_at.asc())
    )
    logs = result.scalars().all()

    # Enrich with performer names
    from app.models.employee import Employee as Emp
    out = []
    for log in logs:
        name = None
        if log.performed_by:
            r = await db.execute(select(Emp).where(Emp.id == log.performed_by))
            emp = r.scalars().first()
            name = emp.full_name or emp.email if emp else None
        out.append(ActivityLogResponse(
            id=log.id,
            task_id=log.task_id,
            action=log.action,
            detail=log.detail,
            performed_by=log.performed_by,
            performer_name=name,
            created_at=log.created_at,
        ))
    return out
