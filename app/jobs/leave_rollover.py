

"""app/jobs/leave_rollover.py — Monthly Leave Balance Rollover Job
=================================================================

Monthly leave balance rollover job.

What it does
────────────
Runs on the 1st of every month (or can be triggered manually).

For every active employee × every active leave type:
  1. Fetch last month's closing_balance.
  2. New month opening_balance = last month's closing_balance
     (no cap — unlimited carry-forward per your business rule).
     Exception: comp_off opening also carries forward unlimited.
     NOTE: closing_balance CAN be negative (casual leave debt).
           A negative opening carries forward as a debt so the
           monthly +1 accrual offsets it first.
  3. New month accrued:
       - casual  → 1  (1 leave per month, your rule)
       - comp_off → 0  (earned only via approved comp_off requests)
  4. used = 0, adjusted = 0  (fresh slate for the new month)
  5. closing_balance = opening + accrued - used + adjusted

If no previous month row exists (new employee's first rollover):
  opening_balance = 0

How to schedule
───────────────
Option A — APScheduler (recommended for simple setups):

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.jobs.leave_rollover import run_leave_rollover

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_leave_rollover,
        trigger="cron",
        day=1,
        hour=0,
        minute=5,
        id="monthly_leave_rollover",
    )
    scheduler.start()

    Add the above to app/main.py inside the lifespan context manager.

Option B — Call manually via an admin endpoint for testing:

    @router.post("/admin/trigger-rollover")
    async def trigger_rollover(db=Depends(get_db), admin=Depends(require_admin)):
        await run_leave_rollover(db)
        return {"message": "Rollover complete"}
"""

from calendar import monthrange
from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.holiday import Holiday
from app.models.leave_wfh_request import LeaveWFHRequest


# ── Config ────────────────────────────────────────────────────
CASUAL_ACCRUAL_PER_MONTH: float = 1.0   # 1 leave per month
LEAVE_TYPES_TO_ACCRUE = ["casual"]       # only casual auto-accrues monthly
ALL_BALANCE_TYPES     = ["casual", "comp_off"]  # rows created for each


# ── Core logic ────────────────────────────────────────────────

def _prev_month(year: int, month: int) -> tuple[int, int]:
    """Return (year, month) for the month before the given one."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


async def _get_approved_leave_days(
    db: AsyncSession,
    employee_id,
    year: int,
    month: int,
) -> tuple[int, int]:
    """
    Return (casual_days, comp_off_days) of approved leave working days
    that fall within the given year/month.

    Priority chain (mirrors the display logic):
      - If the employee had comp_off balance > 0 at the start of that month,
        leave days are charged to comp_off first, then casual.
      - For simplicity at rollover time we charge ALL leave days to casual
        and ALL comp_off-earned days stay in comp_off.accrued.
        The virtual balance display already handles the priority split;
        the ledger just needs the total used days per type.

    Actual approach: count working days (no weekends, no holidays) of all
    approved leave requests whose dates fall in this month, then split
    using the same comp_off-first priority as the virtual balance.
    """
    # First day and last day of the target month
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    # Fetch all approved leave requests overlapping this month
    result = await db.execute(
        select(LeaveWFHRequest).where(
            LeaveWFHRequest.employee_id == employee_id,
            LeaveWFHRequest.request_type == "leave",
            LeaveWFHRequest.status == "approved",
            LeaveWFHRequest.from_date <= last_day,
            LeaveWFHRequest.to_date >= first_day,
        )
    )
    leave_requests = result.scalars().all()

    if not leave_requests:
        return 0, 0

    # Collect all org IDs to fetch holidays (requests share the same org)
    org_id = leave_requests[0].organization_id
    holiday_result = await db.execute(
        select(Holiday.holiday_date).where(
            Holiday.organization_id == org_id,
            Holiday.holiday_date >= first_day,
            Holiday.holiday_date <= last_day,
        )
    )
    holiday_dates = {row for row in holiday_result.scalars().all()}

    # Count working days that fall within this month
    total_days = 0
    for req in leave_requests:
        current = max(req.from_date, first_day)
        end = min(req.to_date, last_day)
        while current <= end:
            if not _is_weekend(current) and current not in holiday_dates:
                total_days += 1
            current += timedelta(days=1)

    # Fetch the previous month's comp_off closing to decide the split
    prev_year, prev_month = _prev_month(year, month)
    comp_result = await db.execute(
        select(EmployeeLeaveBalance).where(
            EmployeeLeaveBalance.employee_id == employee_id,
            EmployeeLeaveBalance.leave_type == "comp_off",
            EmployeeLeaveBalance.year == prev_year,
            EmployeeLeaveBalance.month == prev_month,
        )
    )
    prev_comp_row = comp_result.scalars().first()
    comp_off_available = float(prev_comp_row.closing_balance or 0) if prev_comp_row else 0.0

    # Also add any comp_off earned THIS month via approved comp_off requests
    comp_earned_result = await db.execute(
        select(LeaveWFHRequest).where(
            LeaveWFHRequest.employee_id == employee_id,
            LeaveWFHRequest.request_type == "comp_off",
            LeaveWFHRequest.status == "approved",
            LeaveWFHRequest.from_date >= first_day,
            LeaveWFHRequest.from_date <= last_day,
        )
    )
    comp_off_available += len(comp_earned_result.scalars().all())

    # Priority: spend comp_off first, then casual
    comp_off_used = min(total_days, max(0.0, comp_off_available))  # can't use more than available
    casual_used = total_days - comp_off_used
    return int(casual_used), int(comp_off_used)


async def rollover_for_employee(
    db: AsyncSession,
    employee_id,
    target_year: int,
    target_month: int,
) -> None:
    """
    Create the balance rows for (employee_id, target_year, target_month).

    used values are computed from approved leave requests for that month
    so the ledger accurately reflects what was actually taken.
    """
    prev_year, prev_month = _prev_month(target_year, target_month)

    # Compute used days from approved leave requests once for both leave types
    casual_used, comp_off_used = await _get_approved_leave_days(
        db, employee_id, target_year, target_month
    )

    for leave_type in ALL_BALANCE_TYPES:

        # ── 1. Skip if already exists ──────────────────────────────
        existing_result = await db.execute(
            select(EmployeeLeaveBalance).where(
                EmployeeLeaveBalance.employee_id == employee_id,
                EmployeeLeaveBalance.leave_type == leave_type,
                EmployeeLeaveBalance.year == target_year,
                EmployeeLeaveBalance.month == target_month,
            )
        )
        if existing_result.scalars().first():
            continue

        # ── 2. Opening = previous month's closing ──────────────────
        prev_result = await db.execute(
            select(EmployeeLeaveBalance).where(
                EmployeeLeaveBalance.employee_id == employee_id,
                EmployeeLeaveBalance.leave_type == leave_type,
                EmployeeLeaveBalance.year == prev_year,
                EmployeeLeaveBalance.month == prev_month,
            )
        )
        prev_row = prev_result.scalars().first()
        opening = float(prev_row.closing_balance) if prev_row else 0.0

        # ── 3. Accrual + used ──────────────────────────────────────
        accrued = CASUAL_ACCRUAL_PER_MONTH if leave_type in LEAVE_TYPES_TO_ACCRUE else 0.0
        used = float(casual_used if leave_type == "casual" else comp_off_used)

        # ── 4. Build row ───────────────────────────────────────────
        closing = opening + accrued - used
        db.add(EmployeeLeaveBalance(
            employee_id=employee_id,
            leave_type=leave_type,
            year=target_year,
            month=target_month,
            opening_balance=opening,
            accrued=accrued,
            used=used,
            adjusted=0.0,
            closing_balance=closing,
        ))

    await db.flush()


async def run_leave_rollover(
    db: AsyncSession | None = None,
    target_year: int | None = None,
    target_month: int | None = None,
) -> dict:
    """
    Main entry point.

    Parameters
    ──────────
    db            — pass an existing AsyncSession (e.g. from an admin endpoint),
                    or leave None to open a fresh session from AsyncSessionLocal.
    target_year   — year to create balance rows for. Defaults to today.
    target_month  — month to create balance rows for. Defaults to today.

    Returns a summary dict with counts for logging / admin response.
    """
    today = date.today()
    year  = target_year  or today.year
    month = target_month or today.month

    own_session = db is None
    if own_session:
        db = AsyncSessionLocal()

    try:
        # Fetch all active employees
        result = await db.execute(
            select(Employee).where(Employee.is_active == True)
        )
        employees: Sequence[Employee] = result.scalars().all()

        for emp in employees:
            await rollover_for_employee(db, emp.id, year, month)

        await db.commit()

        return {
            "status": "ok",
            "target": f"{year}-{month:02d}",
            "employees_processed": len(employees),
        }

    except Exception:
        await db.rollback()
        raise

    finally:
        if own_session:
            await db.close()