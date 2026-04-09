# app/services/calendar_service.py
"""
Calendar service — builds date-wise grouped leave/wfh data for a given month.

Single DB query fetches all approved leave and wfh requests that overlap
the target month. Date expansion and grouping is done in Python to avoid
N+1 queries and complex SQL date series.
"""

import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.leave_wfh_request import LeaveWFHRequest
from app.schemas.calendar import CalendarDayEntry, CalendarResponse


async def get_monthly_calendar(
    db: AsyncSession,
    organization_id,
    month: int,
    year: int,
) -> CalendarResponse:
    start_of_month = date(year, month, 1)
    end_of_month = date(year, month, calendar.monthrange(year, month)[1])

    stmt = (
        select(LeaveWFHRequest, Employee.full_name)
        .join(Employee, Employee.id == LeaveWFHRequest.employee_id)
        .where(
            LeaveWFHRequest.organization_id == organization_id,
            LeaveWFHRequest.status == "approved",
            LeaveWFHRequest.request_type.in_(["leave", "wfh"]),
            LeaveWFHRequest.from_date <= end_of_month,
            LeaveWFHRequest.to_date >= start_of_month,
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    grouped: Dict[str, List[CalendarDayEntry]] = defaultdict(list)

    for req, employee_name in rows:
        # Clamp range to within the target month
        range_start = max(req.from_date, start_of_month)
        range_end = min(req.to_date, end_of_month)

        current = range_start
        while current <= range_end:
            key = current.isoformat()  # "2026-04-10"
            grouped[key].append(
                CalendarDayEntry(
                    employee_name=employee_name or "Unknown",
                    type=req.request_type,
                )
            )
            current += timedelta(days=1)

    # Sort by date key for consistent response ordering
    sorted_data = dict(sorted(grouped.items()))

    return CalendarResponse(month=month, year=year, data=sorted_data)
