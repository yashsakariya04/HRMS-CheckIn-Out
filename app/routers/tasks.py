import uuid
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user
from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee
from app.models.task_entry import TaskEntry

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TaskCreateRequest(BaseModel):
    project_id: uuid.UUID
    description: str
    hours: float


class TaskOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    project_id: uuid.UUID
    description: str
    hours_logged: float
    sort_order: int

    model_config = {"from_attributes": True}


async def _get_open_session_today(db: AsyncSession, employee_id) -> AttendanceSession:
    result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.session_date == date.today(),
        )
    )
    session = result.scalars().first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not checked in today. Please check in before logging tasks.",
        )
    if session.check_out_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your session is already closed. Tasks can only be added while checked in.",
        )
    return session


@router.get("/today", response_model=List[TaskOut])
async def get_tasks_today(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    session_result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.employee_id == current_user.id,
            AttendanceSession.session_date == date.today(),
        )
    )
    session = session_result.scalars().first()
    if not session:
        return []

    tasks_result = await db.execute(
        select(TaskEntry)
        .where(TaskEntry.session_id == session.id)
        .order_by(TaskEntry.sort_order, TaskEntry.created_at)
    )
    return tasks_result.scalars().all()


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    if body.hours <= 0 or body.hours > 24:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="hours must be between 0 (exclusive) and 24 (inclusive).",
        )

    session = await _get_open_session_today(db, current_user.id)

    count_result = await db.execute(
        select(TaskEntry).where(TaskEntry.session_id == session.id)
    )
    existing_count = len(count_result.scalars().all())

    task = TaskEntry(
        session_id=session.id,
        project_id=body.project_id,
        employee_id=current_user.id,
        description=body.description,
        hours_logged=body.hours,
        sort_order=existing_count,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    task_result = await db.execute(
        select(TaskEntry).where(
            TaskEntry.id == task_id,
            TaskEntry.employee_id == current_user.id,
        )
    )
    task = task_result.scalars().first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or you do not have permission to delete it.",
        )

    session_result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.id == task.session_id,
            AttendanceSession.check_out_at == None,
        )
    )
    if not session_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete tasks from a closed session.",
        )

    await db.delete(task)
    await db.commit()
