# app/routers/tasks.py
"""
Task entry routes for the Reporting/Dashboard page.

GET    /api/v1/tasks/today            - list today's task entries (populated on page load)
POST   /api/v1/tasks                  - save a new task (Save button)
DELETE /api/v1/tasks/{task_id}        - delete a task (trash icon)
"""

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee
from app.models.task_entry import TaskEntry

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ─── Pydantic schemas (local — small enough to keep here) ──────────────────

class TaskCreateRequest(BaseModel):
    """Body for POST /tasks — what the frontend sends when clicking Save."""
    project_id: uuid.UUID
    description: str
    hours: float             # maps to hours_logged in DB


class TaskOut(BaseModel):
    """What we send back for every task row."""
    id: uuid.UUID
    session_id: uuid.UUID
    project_id: uuid.UUID
    description: str
    hours_logged: float
    sort_order: int

    model_config = {"from_attributes": True}


# ─── Helper ────────────────────────────────────────────────────────────────

def _get_open_session_today(db: Session, employee_id: uuid.UUID) -> AttendanceSession:
    """
    Returns today's OPEN session (check_out_at IS NULL).
    Raises 404 if the employee hasn't checked in today.
    Raises 409 if the session is already closed (checked out).
    Tasks can only be added to an open session.
    """
    today = date.today()
    session = db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == employee_id,
        AttendanceSession.session_date == today,
    ).first()

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


# ─── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/today", response_model=List[TaskOut])
def get_tasks_today(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Returns all tasks the employee has logged today.

    Frontend calls this on page load to restore the task list
    (so tasks don't disappear if the user refreshes the browser).
    Returns [] if no tasks yet or no session today.
    """
    today = date.today()
    session = db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == current_user.id,
        AttendanceSession.session_date == today,
    ).first()

    if not session:
        return []

    tasks = db.query(TaskEntry).filter(
        TaskEntry.session_id == session.id,
    ).order_by(TaskEntry.sort_order, TaskEntry.created_at).all()

    return tasks


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Save a task entry — triggered by the 'Save' button on the Reporting form.

    Rules:
        - Employee must be checked in (open session exists today)
        - hours must be > 0 and <= 24
        - project_id must point to an existing project in the org

    The task is linked to today's open attendance_session automatically.
    """
    # Validate hours range
    if body.hours <= 0 or body.hours > 24:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="hours must be between 0 (exclusive) and 24 (inclusive).",
        )

    # Must be checked in
    session = _get_open_session_today(db, current_user.id)

    # Determine sort order — append at end
    existing_count = db.query(TaskEntry).filter(
        TaskEntry.session_id == session.id
    ).count()

    task = TaskEntry(
        session_id=session.id,
        project_id=body.project_id,
        employee_id=current_user.id,
        description=body.description,
        hours_logged=body.hours,
        sort_order=existing_count,   # 0-indexed, append to end
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Delete a task entry — triggered by the trash/delete icon.

    Rules:
        - Employee can only delete their OWN tasks
        - Session must still be open (cannot delete after checkout)
    """
    task = db.query(TaskEntry).filter(
        TaskEntry.id == task_id,
        TaskEntry.employee_id == current_user.id,   # ownership check
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or you do not have permission to delete it.",
        )

    # Ensure session is still open
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == task.session_id,
        AttendanceSession.check_out_at == None,
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete tasks from a closed session.",
        )

    db.delete(task)
    db.commit()
