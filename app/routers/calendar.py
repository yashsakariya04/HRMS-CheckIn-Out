# app/routers/calendar.py
"""
Calendar routes.

GET /api/v1/calendar  - date-wise approved leave/wfh for a given month
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.employee import Employee
from app.schemas.calendar import CalendarResponse
from app.services import calendar_service

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("", response_model=CalendarResponse)
def get_calendar(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Returns date-wise grouped approved leave and wfh entries for the given month.
    Defaults to current month/year if not provided.
    """
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    return calendar_service.get_monthly_calendar(
        db,
        current_user.organization_id,
        target_month,
        target_year,
    )
