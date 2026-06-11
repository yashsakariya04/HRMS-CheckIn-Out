"""
app/services/balance_service.py — Shared real-time leave balance helper
"""

from calendar import monthrange
from datetime import date, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.holiday import Holiday
from app.models.leave_wfh_request import LeaveWFHRequest
from app.jobs.leave_rollover import _is_in_probation


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


async def compute_realtime_balance(
    db: AsyncSession,
    employee_id,
    bulk_data: dict | None = None,
) -> dict:
    """
    Returns real-time casual and comp_off balance for an employee.

    Logic (mirrors the spreadsheet):
      1. Get the latest ledger row per leave type (last rollover result).
      2. If the current month has no ledger row yet, simulate it:
           opening = last closing, accrued = +1 for casual (0 if in probation)
      3. Count approved leave working days in the current month
         that are NOT yet captured in the ledger's `used` field.
      4. closing = ledger_closing - unapplied_current_month_days

    This means the balance is always real-time accurate, same for
    both admin and employee views.

    Parameters:
      bulk_data — Optional pre-fetched data dict with keys:
                  'balances', 'employees', 'leave_requests', 'holidays'
                  Used by get_leave_summary to avoid N+1 queries.
    """
    today = date.today()
    cur_year, cur_month = today.year, today.month

    # ── 1. Latest ledger row per leave type ───────────────────────────
    if bulk_data and 'balances' in bulk_data:
        rows = bulk_data['balances'].get(employee_id, [])
    else:
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

    seen: set = set()
    latest: dict[str, EmployeeLeaveBalance] = {}
    for row in rows:
        if row.leave_type not in seen:
            seen.add(row.leave_type)
            latest[row.leave_type] = row

    casual_row = latest.get("casual")
    comp_row = latest.get("comp_off")

    # ── Fetch employee's joined_on for probation check ─────────────────
    if bulk_data and 'employees' in bulk_data:
        joined_on = bulk_data['employees'].get(employee_id)
    else:
        emp_result = await db.execute(
            select(Employee.joined_on).where(Employee.id == employee_id)
        )
        joined_on = emp_result.scalar_one_or_none()
    
    in_probation = _is_in_probation(joined_on, cur_year, cur_month)
    simulated_accrual = 0.0 if in_probation else 1.0

    # ── 2. Base closing from ledger (or simulate if no row yet) ───────
    if casual_row and casual_row.year == cur_year and casual_row.month == cur_month:
        casual_base = float(casual_row.closing_balance or 0)
        casual_already_used = float(casual_row.used)
    elif casual_row:
        casual_base = float(casual_row.closing_balance or 0) + simulated_accrual
        casual_already_used = 0.0
    else:
        casual_base = simulated_accrual
        casual_already_used = 0.0

    if comp_row and comp_row.year == cur_year and comp_row.month == cur_month:
        comp_base = float(comp_row.closing_balance or 0)
        comp_already_used = float(comp_row.used)
    elif comp_row:
        comp_base = float(comp_row.closing_balance or 0)
        comp_already_used = 0.0
    else:
        comp_base = 0.0
        comp_already_used = 0.0

    # ── 3. Count approved leave days in current month not yet in ledger ─
    first_day = date(cur_year, cur_month, 1)
    last_day = date(cur_year, cur_month, monthrange(cur_year, cur_month)[1])

    if bulk_data and 'leave_requests' in bulk_data:
        leave_requests = bulk_data['leave_requests'].get(employee_id, [])
    else:
        leave_result = await db.execute(
            select(LeaveWFHRequest).where(
                LeaveWFHRequest.employee_id == employee_id,
                LeaveWFHRequest.request_type == "leave",
                LeaveWFHRequest.status == "approved",
                LeaveWFHRequest.from_date <= last_day,
                LeaveWFHRequest.to_date >= first_day,
            )
        )
        leave_requests = leave_result.scalars().all()

    current_month_used = 0.0
    if leave_requests:
        if bulk_data and 'holidays' in bulk_data:
            holiday_dates = bulk_data['holidays']
        else:
            org_id = leave_requests[0].organization_id
            holiday_result = await db.execute(
                select(Holiday.holiday_date).where(
                    Holiday.organization_id == org_id,
                    Holiday.holiday_date >= first_day,
                    Holiday.holiday_date <= last_day,
                )
            )
            holiday_dates = set(holiday_result.scalars().all())

        for req in leave_requests:
            current = max(req.from_date, first_day)
            end = min(req.to_date, last_day)
            while current <= end:
                if not _is_weekend(current) and current not in holiday_dates:
                    current_month_used += 1
                current += timedelta(days=1)

    # ── 4. Split current month used days: comp_off first, then casual ──
    comp_off_available = max(0.0, comp_base)
    comp_off_unapplied = min(current_month_used, comp_off_available) - comp_already_used
    casual_unapplied = (current_month_used - min(current_month_used, comp_off_available)) - casual_already_used

    casual_balance = casual_base - casual_unapplied
    comp_balance = comp_base - comp_off_unapplied

    return {
        "casual_balance": casual_balance,
        "casual_used": current_month_used,
        "comp_off_balance": comp_balance,
        "comp_off_used": comp_already_used + comp_off_unapplied,
    }


async def get_balance_rows(db: AsyncSession, employee_id) -> List[EmployeeLeaveBalance]:
    """Return latest ledger rows per leave type (for /balances/me endpoint)."""
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
    seen: set = set()
    latest = []
    for row in rows:
        if row.leave_type not in seen:
            seen.add(row.leave_type)
            latest.append(row)
    return latest

