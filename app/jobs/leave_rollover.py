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
from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance


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


async def rollover_for_employee(
    db: AsyncSession,
    employee_id,
    target_year: int,
    target_month: int,
) -> None:
    """
    Create (or update if already exists) the balance rows for
    (employee_id, target_year, target_month) for every leave type.
    """
    prev_year, prev_month = _prev_month(target_year, target_month)

    for leave_type in ALL_BALANCE_TYPES:

        # ── 1. Check if target month row already exists ────────────
        existing_result = await db.execute(
            select(EmployeeLeaveBalance).where(
                EmployeeLeaveBalance.employee_id == employee_id,
                EmployeeLeaveBalance.leave_type == leave_type,
                EmployeeLeaveBalance.year == target_year,
                EmployeeLeaveBalance.month == target_month,
            )
        )
        existing = existing_result.scalars().first()
        if existing:
            # Already rolled over — skip to avoid double-accrual.
            continue

        # ── 2. Fetch previous month's closing balance ──────────────
        prev_result = await db.execute(
            select(EmployeeLeaveBalance).where(
                EmployeeLeaveBalance.employee_id == employee_id,
                EmployeeLeaveBalance.leave_type == leave_type,
                EmployeeLeaveBalance.year == prev_year,
                EmployeeLeaveBalance.month == prev_month,
            )
        )
        prev_row = prev_result.scalars().first()

        # Carry forward last month's closing (could be negative for casual).
        # If no prior row (new employee) → start at 0.
        opening = float(prev_row.closing_balance) if prev_row else 0.0

        # ── 3. Monthly accrual ─────────────────────────────────────
        # casual: +1 every month
        # comp_off: 0 (earned only via approved comp_off requests)
        accrued = CASUAL_ACCRUAL_PER_MONTH if leave_type in LEAVE_TYPES_TO_ACCRUE else 0.0

        # ── 4. Build the new row ───────────────────────────────────
        closing = opening + accrued  # used=0, adjusted=0 for a fresh month
        new_row = EmployeeLeaveBalance(
            employee_id=employee_id,
            leave_type=leave_type,
            year=target_year,
            month=target_month,
            opening_balance=opening,
            accrued=accrued,
            used=0.0,
            adjusted=0.0,
            closing_balance=closing,
        )
        db.add(new_row)

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
            select(Employee).where(Employee.is_active is True)
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