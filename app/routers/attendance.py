# app/routers/attendance.py
"""
Attendance routes.

GET  /api/v1/attendance/today      - today's session or null
POST /api/v1/attendance/check-in   - create session + tasks
PATCH /api/v1/attendance/check-out - close open session
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import date

from fastapi import Query
from fastapi.responses import StreamingResponse
import io
from app.schemas.attendance import SessionListResponse
from app.database import get_db
from app.dependencies import get_current_user
from app.models.employee import Employee
from app.models.attendance_session import AttendanceSession
from app.schemas.attendance import CheckInRequest, SessionResponse
from app.services import attendance_service

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.get("/today", response_model=Optional[SessionResponse])
def get_today(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Returns today's session or null.

    Frontend uses this on page load to decide:
        null     → show check-in form
        session  → show check-out button + today's tasks

    Also used to restore state if user refreshes the page mid-session.
    """
    session = attendance_service.get_today_session(db, current_user.id)
    return session


@router.post(
    "/check-in",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def check_in(
    body: CheckInRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Check in for today with tasks.

    Body:
        {
            "tasks": [
                {
                    "project_id": "uuid",
                    "description": "Fixed login bug",
                    "hours": 3.0
                }
            ]
        }

    Returns the created session with tasks.
    Fails with 409 if already checked in today.
    """
    session = attendance_service.check_in(
        db=db,
        employee_id=current_user.id,
        organization_id=current_user.organization_id,
        body=body,
    )
    return session


@router.patch("/check-out", response_model=SessionResponse)
def check_out(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Check out — closes today's open session.
    No request body needed — backend finds the open session automatically.
    Computes and stores total_hours on the session.
    Fails with 404 if not checked in today.
    """
    session = attendance_service.check_out(
        db=db,
        employee_id=current_user.id,
    )
    return session


@router.get("/avg-hours")
def get_avg_hours(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Returns the average total_hours across ALL completed sessions
    (sessions with check_out_at set) for the current calendar month.

    Powers the 'AVG. TIME' metric card on the dashboard.
    Returns: { "avg_hours": 5.7 } or { "avg_hours": 0 } if no sessions yet.
    """
    today = date.today()
    result = db.query(
        func.avg(AttendanceSession.total_hours)
    ).filter(
        AttendanceSession.employee_id == current_user.id,
        func.extract('year',  AttendanceSession.session_date) == today.year,
        func.extract('month', AttendanceSession.session_date) == today.month,
        AttendanceSession.check_out_at.isnot(None),   # only completed sessions
    ).scalar()

    avg = round(float(result), 2) if result else 0.0
    return {"avg_hours": avg}


@router.get("/sessions/download")
def download_sessions_csv(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Download monthly attendance as CSV.
    /sessions/download must be defined BEFORE /sessions/{id}
    so FastAPI does not try to match 'download' as a UUID.
    """
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    sessions = attendance_service.get_sessions_for_month(
        db, current_user.id, target_month, target_year
    )
    csv_str = attendance_service.generate_csv(sessions)

    month_name = date(target_year, target_month, 1).strftime("%B").lower()
    filename = f"attendance_{month_name}_{target_year}.csv"

    return StreamingResponse(
        io.StringIO(csv_str),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/sessions", response_model=List[SessionListResponse])
def get_sessions(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Returns all sessions for the given month/year for the logged-in employee.
    Defaults to current month/year if not provided.
    Powers the Daily tasks page table.
    """
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    return attendance_service.get_sessions_for_month(
        db, current_user.id, target_month, target_year
    )

