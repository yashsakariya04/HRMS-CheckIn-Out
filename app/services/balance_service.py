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

from calendar import monthrange
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

    Virtual balance = latest_ledger_closing - future_approved_leave_days

    This ensures that if a leave is approved for a future month (before
    rollover runs), the balance shown immediately reflects that deduction.

    Args:
        db:          Async database session.
        employee_id: UUID of the employee (as string or UUID object).

    Returns:
        List of EmployeeLeaveBalance ORM objects — one per leave type.
        The closing_balance field is adjusted to reflect future deductions.
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

    # Compute the last day of the latest ledger month
    latest_row = latest[0]
    last_ledger_day = date(
        latest_row.year,
        latest_row.month,
        monthrange(latest_row.year, latest_row.month)[1],
    )

    # Fetch all approved leave requests AFTER the latest ledger month
    future_result = await db.execute(
        select(LeaveWFHRequest).where(
            LeaveWFHRequest.employee_id == employee_id,
            LeaveWFHRequest.request_type == "leave",
            LeaveWFHRequest.status == "approved",
            LeaveWFHRequest.from_date > last_ledger_day,
        )
    )
    future_requests = future_result.scalars().all()

    if not future_requests:
        return latest

    # Count working days (no weekends, no holidays) in future requests
    org_id = future_requests[0].organization_id
    min_date = min(req.from_date for req in future_requests)
    max_date = max(req.to_date for req in future_requests)

    holiday_result = await db.execute(
        select(Holiday.holiday_date).where(
            Holiday.organization_id == org_id,
            Holiday.holiday_date >= min_date,
            Holiday.holiday_date <= max_date,
        )
    )
    holiday_dates = {row for row in holiday_result.scalars().all()}

    future_days = 0
    for req in future_requests:
        current = req.from_date
        while current <= req.to_date:
            if not _is_weekend(current) and current not in holiday_dates:
                future_days += 1
            current += timedelta(days=1)

    # Adjust closing_balance for casual (comp_off priority handled at display time)
    for row in latest:
        if row.leave_type == "casual":
            row.closing_balance = float(row.closing_balance or 0) - future_days
            break

    return latest
