from datetime import date
from typing import Optional, List
import io

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user
from app.models.employee import Employee
from app.models.attendance_session import AttendanceSession
from app.schemas.attendance import CheckInRequest, SessionResponse, SessionListResponse
from app.services import attendance_service

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.get("/today", response_model=Optional[SessionResponse])
async def get_today(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return await attendance_service.get_today_session(db, current_user.id)


@router.post("/check-in", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def check_in(
    body: CheckInRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return await attendance_service.check_in(
        db=db,
        employee_id=current_user.id,
        organization_id=current_user.organization_id,
        body=body,
    )


@router.patch("/check-out", response_model=SessionResponse)
async def check_out(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return await attendance_service.check_out(db=db, employee_id=current_user.id)


@router.get("/avg-hours")
async def get_avg_hours(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    today = date.today()
    result = await db.execute(
        select(func.avg(AttendanceSession.total_hours)).where(
            AttendanceSession.employee_id == current_user.id,
            func.extract("year", AttendanceSession.session_date) == today.year,
            func.extract("month", AttendanceSession.session_date) == today.month,
            AttendanceSession.check_out_at.isnot(None),
        )
    )
    avg = result.scalar()
    return {"avg_hours": round(float(avg), 2) if avg else 0.0}


@router.get("/sessions/download")
async def download_sessions_csv(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    sessions = await attendance_service.get_sessions_for_month(db, current_user.id, target_month, target_year)
    csv_str = attendance_service.generate_csv(sessions)

    month_name = date(target_year, target_month, 1).strftime("%B").lower()
    filename = f"attendance_{month_name}_{target_year}.csv"

    return StreamingResponse(
        io.StringIO(csv_str),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sessions", response_model=List[SessionListResponse])
async def get_sessions(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    return await attendance_service.get_sessions_for_month(db, current_user.id, target_month, target_year)
