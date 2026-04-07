# app/services/leaves_service.py
"""
Leaves service — builds current and previous month leave history for an employee.

Single DB query fetches all approved leave requests for the employee.
Date expansion, deduplication, and grouping is done in Python.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models.leave_wfh_request import LeaveWFHRequest
from app.schemas.leaves import CurrentMonthLeaves, LeavesResponse, PreviousMonthLeaves


def get_my_leaves(db: Session, employee_id) -> LeavesResponse:
    """
    Return current month leave dates and previous months leave history.

    Steps:
        1. Fetch all approved leave requests for the employee
        2. Expand each date range into individual dates
        3. Deduplicate dates (in case of overlapping requests)
        4. Split into current month vs previous months
        5. Group previous months by (year, month), sorted descending
    """
    today = date.today()

    rows = db.query(LeaveWFHRequest).filter(
        LeaveWFHRequest.employee_id == employee_id,
        LeaveWFHRequest.status == "approved",
        LeaveWFHRequest.request_type == "leave",
    ).all()

    # Expand all date ranges — use a set to avoid duplicates
    all_dates: set[date] = set()
    for req in rows:
        current = req.from_date
        while current <= req.to_date:
            all_dates.add(current)
            current += timedelta(days=1)

    # Split into current month and previous months
    current_month_dates: List[date] = []
    previous_dates: List[date] = []

    for d in all_dates:
        if d.year == today.year and d.month == today.month:
            current_month_dates.append(d)
        elif d < today.replace(day=1):  # strictly before current month
            previous_dates.append(d)

    # Build current month response
    current_month = CurrentMonthLeaves(
        month=today.month,
        year=today.year,
        dates=sorted(d.isoformat() for d in current_month_dates),
    )

    # Group previous months by (year, month)
    grouped: dict[tuple, List[date]] = defaultdict(list)
    for d in previous_dates:
        grouped[(d.year, d.month)].append(d)

    # Sort months descending (latest first), dates ascending within each month
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
