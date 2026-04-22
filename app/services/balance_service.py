"""
app/services/balance_service.py — Leave Balance Query Service
=============================================================
Provides helper functions for fetching leave balance records.

Non-technical summary:
----------------------
This service computes the employee's real-time leave balance by:
  1. Fetching the latest ledger row per leave type (most recent month).
  2. Subtracting any approved future leave days not yet in the ledger.

This ensures the balance shown is always accurate even if leaves are
approved for future months before the rollover job runs.
"""

from datetime import date, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.holiday import Holiday
from app.models.leave_wfh_request import LeaveWFHRequest


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


async def _get_current_month_balances(
    db: AsyncSession, employee_id
) -> List[EmployeeLeaveBalance]:
    """
    Return the latest leave balance row per leave type with virtual balance.

    Virtual balance = latest_ledger_closing - unapplied_approved_leave_days

    Unapplied days = all approved leave working days that fall AFTER the
    latest ledger row was created (including current month if the ledger
    was created before the leave was approved).

    Args:
        db:          Async database session.
        employee_id: UUID of the employee (as string or UUID object).

    Returns:
        List of EmployeeLeaveBalance ORM objects — one per leave type.
        The closing_balance field is adjusted to reflect unapplied deductions.
    """
    # Fetch all balance rows ordered latest-first
    result = await db.execute(
        select(EmployeeLeaveBalance)
        .where(EmployeeLeaveBalance.employee_id == employee_id)
        .order_by(
            EmployeeLeaveBalance.leave_type,
            EmployeeLeaveBalance.year.desc(),
            EmployeeLeaveBalance.month.desc(),
        )
    )
    rows = result.scalars().all()

    # Keep only the latest row per leave type
    seen: set = set()
    latest: List[EmployeeLeaveBalance] = []
    for row in rows:
        if row.leave_type not in seen:
            seen.add(row.leave_type)
            latest.append(row)

    if not latest:
        return []

    # Fetch all approved leave requests (any month)
    all_requests_result = await db.execute(
        select(LeaveWFHRequest).where(
            LeaveWFHRequest.employee_id == employee_id,
            LeaveWFHRequest.request_type == "leave",
            LeaveWFHRequest.status == "approved",
        )
    )
    all_requests = all_requests_result.scalars().all()

    if not all_requests:
        return latest

    # Count working days NOT yet reflected in the ledger
    # (i.e. days that fall in months where the ledger row doesn't have them in `used`)
    org_id = all_requests[0].organization_id
    min_date = min(req.from_date for req in all_requests)
    max_date = max(req.to_date for req in all_requests)

    holiday_result = await db.execute(
        select(Holiday.holiday_date).where(
            Holiday.organization_id == org_id,
            Holiday.holiday_date >= min_date,
            Holiday.holiday_date <= max_date,
        )
    )
    holiday_dates = {row for row in holiday_result.scalars().all()}

    # For each request, count working days that are NOT in a rolled-over month
    # A month is "rolled over" if a ledger row exists for it with used > 0
    # For simplicity: count ALL approved leave working days, then subtract
    # what's already in the ledger's `used` field
    total_approved_days = 0
    for req in all_requests:
        current = req.from_date
        while current <= req.to_date:
            if not _is_weekend(current) and current not in holiday_dates:
                total_approved_days += 1
            current += timedelta(days=1)

    # The ledger's `used` field already accounts for some of these days
    # (if rollover ran for that month). Subtract that to avoid double-counting.
    casual_row = next((r for r in latest if r.leave_type == "casual"), None)
    if casual_row:
        already_in_ledger = float(casual_row.used)
        unapplied_days = total_approved_days - already_in_ledger
        casual_row.closing_balance = float(casual_row.closing_balance or 0) - unapplied_days

    return latest
