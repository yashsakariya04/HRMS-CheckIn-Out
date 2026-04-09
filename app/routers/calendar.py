"""
app/routers/calendar.py — Monthly Leave Calendar Endpoint
==========================================================
Returns a date-wise view of approved leave and WFH for a given month,
used to populate the team calendar on the frontend.

Endpoint:
  GET /api/v1/calendar?month=4&year=2025
    — Returns all approved leave/WFH entries for the specified month,
      grouped by date. Defaults to the current month if not specified.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.calendar import CalendarResponse
from app.services import calendar_service

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("", response_model=CalendarResponse)
async def get_calendar(
    month: Optional[int] = Query(None, ge=1, le=12),   # 1-12, defaults to current month
    year: Optional[int] = Query(None, ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Return the team leave/WFH calendar for a given month.

    Shows all approved leave and WFH requests for the organization,
    grouped by date. Each date lists the employees on leave/WFH that day.

    Defaults to the current month and year if not provided.
    """
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    return await calendar_service.get_monthly_calendar(
        db,
        current_user.organization_id,
        target_month,
        target_year,
    )
