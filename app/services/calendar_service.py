"""
app/services/calendar_service.py — Monthly Calendar Business Logic
==================================================================
Builds the date-wise leave/WFH calendar for a given month.

Non-technical summary:
----------------------
This service fetches all approved leave and WFH requests that overlap
a target month, then expands each request's date range into individual
dates and groups them by date.

Single DB query → Python-side date expansion → grouped dict response.
This avoids N+1 queries and complex SQL date series generation.
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
    """
    Return a date-keyed dict of all employees' approved leave/WFH entries
    for the given month across the entire organization.

    Steps:
      1. Query all approved leave/wfh requests overlapping the month for the org.
      2. For each request, expand the date range (clamped to the month).
      3. Group full entry details by ISO date string.
      4. Return sorted by date.

    Args:
        db:              Async database session.
        organization_id: Only return requests for this organization.
        month:           Target month (1-12).
        year:            Target year.

    Returns:
        CalendarResponse with month, year, and data dict.
    """
    start_of_month = date(year, month, 1)
    end_of_month = date(year, month, calendar.monthrange(year, month)[1])

    stmt = (
        select(LeaveWFHRequest, Employee.full_name, Employee.email)
        .join(Employee, Employee.id == LeaveWFHRequest.employee_id)
        .where(
            LeaveWFHRequest.organization_id == organization_id,
            LeaveWFHRequest.status == "approved",
            LeaveWFHRequest.request_type.in_(["leave", "wfh"]),
            # Overlapping range: request starts before month ends AND ends after month starts
            LeaveWFHRequest.from_date <= end_of_month,
            LeaveWFHRequest.to_date >= start_of_month,
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    grouped: Dict[str, List[CalendarDayEntry]] = defaultdict(list)

    for req, employee_name, employee_email in rows:
        # Clamp the request range to within the target month
        range_start = max(req.from_date, start_of_month)
        range_end = min(req.to_date, end_of_month)

        current = range_start
        while current <= range_end:
            key = current.isoformat()  # e.g. "2025-04-10"
            grouped[key].append(
                CalendarDayEntry(
                    employee_id=req.employee_id,
                    employee_name=employee_name or "Unknown",
                    employee_email=employee_email,
                    type=req.request_type,
                    from_date=req.from_date,
                    to_date=req.to_date,
                    reason=req.reason,
                )
            )
            current += timedelta(days=1)

    return CalendarResponse(month=month, year=year, data=dict(sorted(grouped.items())))
