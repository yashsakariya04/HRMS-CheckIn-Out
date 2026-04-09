"""
app/services/leave_service_Emp.py — Employee Leave History Service
==================================================================
Builds the employee's personal leave history response.

Non-technical summary:
----------------------
When an employee opens their leave history page, this service:
  1. Fetches all their approved leave requests from the database.
  2. Expands each request's date range into individual dates.
  3. Splits dates into "this month" and "previous months".
  4. Returns a structured response the frontend can display directly.

Example: A request from April 10–12 becomes dates [Apr 10, Apr 11, Apr 12].
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave_wfh_request import LeaveWFHRequest
from app.schemas.leaves import CurrentMonthLeaves, LeavesResponse, PreviousMonthLeaves


async def get_my_leaves(db: AsyncSession, employee_id) -> LeavesResponse:
    """
    Return the employee's approved leave history grouped by month.

    Fetches all approved "leave" type requests, expands date ranges
    into individual dates, then groups them into current month and
    previous months.

    Args:
        db:          Async database session.
        employee_id: UUID of the employee.

    Returns:
        LeavesResponse with current_month dates and previous_months summaries.
    """
    today = date.today()

    # Fetch all approved leave requests for this employee
    result = await db.execute(
        select(LeaveWFHRequest).where(
            LeaveWFHRequest.employee_id == employee_id,
            LeaveWFHRequest.status == "approved",
            LeaveWFHRequest.request_type == "leave",
        )
    )
    rows = result.scalars().all()

    # Expand each request's date range into individual dates
    all_dates: set[date] = set()
    for req in rows:
        current = req.from_date
        while current <= req.to_date:
            all_dates.add(current)
            current += timedelta(days=1)

    # Split into current month vs previous months
    current_month_dates: List[date] = []
    previous_dates: List[date] = []

    for d in all_dates:
        if d.year == today.year and d.month == today.month:
            current_month_dates.append(d)
        elif d < today.replace(day=1):
            previous_dates.append(d)

    current_month = CurrentMonthLeaves(
        month=today.month,
        year=today.year,
        dates=sorted(d.isoformat() for d in current_month_dates),
    )

    # Group previous dates by (year, month) for the summary
    grouped: dict[tuple, List[date]] = defaultdict(list)
    for d in previous_dates:
        grouped[(d.year, d.month)].append(d)

    previous_months = [
        PreviousMonthLeaves(
            month=month,
            year=year,
            total_days=len(dates),
            dates=sorted(d.isoformat() for d in dates),
        )
        for (year, month), dates in sorted(grouped.items(), reverse=True)
    ]

    return LeavesResponse(current_month=current_month, previous_months=previous_months)
