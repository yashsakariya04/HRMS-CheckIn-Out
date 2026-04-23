"""
app/services/leave_service_Emp.py — Employee Leave History Service
==================================================================
Builds the logged-in employee's personal leave history response.

What it returns
───────────────
  current_month   — individual working leave dates in the current calendar month.
  previous_months — per-month totals + dates for every past month that
                    has at least one approved leave working day.

Only "leave" type requests with status "approved" are included.
Comp-off, WFH, and missing-time requests are excluded.

Date expansion
──────────────
Each request covers a from_date → to_date range.  This service expands
every range into individual WORKING dates only (weekends and company
holidays are excluded) so the calendar view matches the balance deduction.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holiday import Holiday
from app.models.leave_wfh_request import LeaveWFHRequest
from app.schemas.leaves import CurrentMonthLeaves, LeavesResponse, PreviousMonthLeaves


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


async def get_my_leaves(db: AsyncSession, employee_id) -> LeavesResponse:
    """
    Return the employee's approved leave history grouped by month.

    Args:
        db:          Async database session.
        employee_id: UUID of the logged-in employee.

    Returns:
        LeavesResponse with:
          • current_month — sorted list of ISO date strings for this month.
          • previous_months — list of PreviousMonthLeaves, newest first.
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

    if not rows:
        return LeavesResponse(
            current_month=CurrentMonthLeaves(month=today.month, year=today.year, dates=[]),
            previous_months=[],
        )

    # Extract scalar values immediately — avoids lazy-load hangs after session moves on
    req_data = [
        (req.from_date, req.to_date, req.organization_id)
        for req in rows
    ]

    # Fetch all holiday dates across the full span of leave requests
    min_date = min(from_date for from_date, _, __ in req_data)
    max_date = max(to_date for _, to_date, __ in req_data)
    org_id = req_data[0][2]

    holiday_dates: set[date] = set()
    if org_id:
        holiday_result = await db.execute(
            select(Holiday.holiday_date).where(
                Holiday.organization_id == org_id,
                Holiday.holiday_date >= min_date,
                Holiday.holiday_date <= max_date,
            )
        )
        holiday_dates = set(holiday_result.scalars().all())

    # Expand each request's date range into individual WORKING dates only
    # (weekends and holidays are excluded — matches balance deduction logic)
    all_dates: set[date] = set()
    for from_date, to_date, _ in req_data:
        d = from_date
        while d <= to_date:
            if not _is_weekend(d) and d not in holiday_dates:
                all_dates.add(d)
            d += timedelta(days=1)

    # Partition into current month vs previous months
    current_month_dates: List[date] = []
    previous_dates: List[date] = []

    first_of_this_month = today.replace(day=1)

    for d in all_dates:
        if d.year == today.year and d.month == today.month:
            current_month_dates.append(d)
        elif d < first_of_this_month:
            previous_dates.append(d)
        # Future-month approved leaves are intentionally excluded from the
        # history view — they will appear once that month becomes current.

    current_month = CurrentMonthLeaves(
        month=today.month,
        year=today.year,
        dates=sorted(d.isoformat() for d in current_month_dates),
    )

    # Group previous dates by (year, month)
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

    return LeavesResponse(
        current_month=current_month,
        previous_months=previous_months,
    )







# """
# app/services/leave_service_Emp.py — Employee Leave History Service
# ==================================================================
# Builds the employee's personal leave history response.

# Non-technical summary:
# ----------------------
# When an employee opens their leave history page, this service:
#   1. Fetches all their approved leave requests from the database.
#   2. Expands each request's date range into individual dates.
#   3. Splits dates into "this month" and "previous months".
#   4. Returns a structured response the frontend can display directly.

# Example: A request from April 10–12 becomes dates [Apr 10, Apr 11, Apr 12].
# """

# from collections import defaultdict
# from datetime import date, timedelta
# from typing import List

# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.leave_wfh_request import LeaveWFHRequest
# from app.schemas.leaves import CurrentMonthLeaves, LeavesResponse, PreviousMonthLeaves


# async def get_my_leaves(db: AsyncSession, employee_id) -> LeavesResponse:
#     """
#     Return the employee's approved leave history grouped by month.

#     Fetches all approved "leave" type requests, expands date ranges
#     into individual dates, then groups them into current month and
#     previous months.

#     Args:
#         db:          Async database session.
#         employee_id: UUID of the employee.

#     Returns:
#         LeavesResponse with current_month dates and previous_months summaries.
#     """
#     today = date.today()

#     # Fetch all approved leave requests for this employee
#     result = await db.execute(
#         select(LeaveWFHRequest).where(
#             LeaveWFHRequest.employee_id == employee_id,
#             LeaveWFHRequest.status == "approved",
#             LeaveWFHRequest.request_type == "leave",
#         )
#     )
#     rows = result.scalars().all()

#     # Expand each request's date range into individual dates
#     all_dates: set[date] = set()
#     for req in rows:
#         current = req.from_date
#         while current <= req.to_date:
#             all_dates.add(current)
#             current += timedelta(days=1)

#     # Split into current month vs previous months
#     current_month_dates: List[date] = []
#     previous_dates: List[date] = []

#     for d in all_dates:
#         if d.year == today.year and d.month == today.month:
#             current_month_dates.append(d)
#         elif d < today.replace(day=1):
#             previous_dates.append(d)

#     current_month = CurrentMonthLeaves(
#         month=today.month,
#         year=today.year,
#         dates=sorted(d.isoformat() for d in current_month_dates),
#     )

#     # Group previous dates by (year, month) for the summary
#     grouped: dict[tuple, List[date]] = defaultdict(list)
#     for d in previous_dates:
#         grouped[(d.year, d.month)].append(d)

#     previous_months = [
#         PreviousMonthLeaves(
#             month=month,
#             year=year,
#             total_days=len(dates),
#             dates=sorted(d.isoformat() for d in dates),
#         )
#         for (year, month), dates in sorted(grouped.items(), reverse=True)
#     ]

#     return LeavesResponse(current_month=current_month, previous_months=previous_months)
