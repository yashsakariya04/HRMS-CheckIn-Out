"""
app/services/balance_service.py — Shared real-time leave balance helper
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


async def compute_realtime_balance(db: AsyncSession, employee_id) -> dict:
    """
    Returns real-time casual and comp_off balance for an employee.

    Logic (mirrors the spreadsheet):
      1. Get the latest ledger row per leave type (last rollover result).
      2. If the current month has no ledger row yet, simulate it:
           opening = last closing, accrued = +1 for casual
      3. Count approved leave working days in the current month
         that are NOT yet captured in the ledger's `used` field.
      4. closing = ledger_closing - unapplied_current_month_days

    This means the balance is always real-time accurate, same for
    both admin and employee views.
    """
    today = date.today()
    cur_year, cur_month = today.year, today.month

    # ── 1. Latest ledger row per leave type ───────────────────────────
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

    # ── 2. Base closing from ledger (or simulate if no row yet) ───────
    if casual_row and casual_row.year == cur_year and casual_row.month == cur_month:
        # Rollover already ran for this month — ledger is the base
        casual_base = float(casual_row.closing_balance or 0)
        casual_already_used = float(casual_row.used)
    elif casual_row:
        # Rollover hasn't run yet for this month — simulate opening + accrual
        casual_base = float(casual_row.closing_balance or 0) + 1.0  # +1 accrual
        casual_already_used = 0.0
    else:
        casual_base = 1.0  # brand new employee: first month accrual
        casual_already_used = 0.0

    if comp_row and comp_row.year == cur_year and comp_row.month == cur_month:
        comp_balance = float(comp_row.closing_balance or 0)
    elif comp_row:
        comp_balance = float(comp_row.closing_balance or 0)
    else:
        comp_balance = 0.0

    # ── 3. Count approved leave days in current month not yet in ledger ─
    first_day = date(cur_year, cur_month, 1)
    last_day = date(cur_year, cur_month, monthrange(cur_year, cur_month)[1])

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

    # ── 4. Unapplied = current month approved days minus what ledger already has ─
    unapplied = current_month_used - casual_already_used
    casual_balance = casual_base - unapplied

    return {
        "casual_balance": casual_balance,
        "casual_used": current_month_used,
        "comp_off_balance": comp_balance,
        "comp_off_used": float(comp_row.used) if comp_row and comp_row.year == cur_year and comp_row.month == cur_month else 0.0,
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



# """
# app/services/balance_service.py — Real-Time Leave Balance Service
# =================================================================

# Core design
# -----------
# The ledger (EmployeeLeaveBalance) is written ONCE per month by the rollover
# job.  Between rollover runs the balance must still be accurate — including
# for leaves approved in a FUTURE month.

# compute_realtime_balance() works in three phases:

#   Phase 1 — Anchor
#       Find the latest ledger row per leave type.
#       That row's closing_balance is the starting point.

#   Phase 2 — Walk forward month by month from the anchor to today (or beyond).
#       For every month that has no ledger row yet, simulate it:
#         • casual:   opening = prev closing,  accrued = +1
#         • comp_off: opening = prev closing,  accrued = 0
#       Count approved leave working days for each month (using the same
#       comp_off-first priority the rollover job uses) and subtract them.

#   Phase 3 — Return the final projected balance for each leave type.

# Result: the displayed balance is ALWAYS accurate — even if:
#   • the employee took leave in the current month before rollover ran,
#   • the admin approved leave for a future month (next-month leave gap fixed),
#   • the employee is brand-new and has no ledger rows at all.
# """

# from calendar import monthrange
# from datetime import date, timedelta
# from typing import List

# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.employee_leave_balance import EmployeeLeaveBalance
# from app.models.holiday import Holiday
# from app.models.leave_wfh_request import LeaveWFHRequest


# # ── Helpers ───────────────────────────────────────────────────────────────────

# def _is_weekend(d: date) -> bool:
#     return d.weekday() >= 5


# def _month_range(year: int, month: int):
#     """Return (first_day, last_day) for the given year/month."""
#     first = date(year, month, 1)
#     last = date(year, month, monthrange(year, month)[1])
#     return first, last


# def _next_month(year: int, month: int):
#     """Return (year, month) for the month after the given one."""
#     if month == 12:
#         return year + 1, 1
#     return year, month + 1


# def _months_from_to(start_year: int, start_month: int, end_year: int, end_month: int):
#     """
#     Yield (year, month) tuples from start (exclusive) to end (inclusive).
#     Used to walk forward from the anchor month to the current (or future) month.
#     """
#     y, m = start_year, start_month
#     while True:
#         y, m = _next_month(y, m)
#         yield y, m
#         if (y, m) == (end_year, end_month):
#             break


# async def _working_days_in_month(
#     db: AsyncSession,
#     organization_id,
#     year: int,
#     month: int,
# ) -> set[date]:
#     """Return the set of holiday dates in the given month for the org."""
#     first, last = _month_range(year, month)
#     result = await db.execute(
#         select(Holiday.holiday_date).where(
#             Holiday.organization_id == organization_id,
#             Holiday.holiday_date >= first,
#             Holiday.holiday_date <= last,
#         )
#     )
#     return set(result.scalars().all())


# def _count_working_days(
#     from_date: date,
#     to_date: date,
#     year: int,
#     month: int,
#     holiday_dates: set[date],
# ) -> float:
#     """
#     Count working days inside a specific (year, month) window for one request.
#     Clips the request range to [first_day_of_month, last_day_of_month].
#     """
#     first, last = _month_range(year, month)
#     start = max(from_date, first)
#     end = min(to_date, last)
#     count = 0.0
#     current = start
#     while current <= end:
#         if not _is_weekend(current) and current not in holiday_dates:
#             count += 1
#         current += timedelta(days=1)
#     return count


# # ── Main public function ──────────────────────────────────────────────────────

# async def compute_realtime_balance(db: AsyncSession, employee_id) -> dict:
#     """
#     Return accurate real-time casual and comp_off balances for an employee.

#     Always reflects ALL approved leaves — including future months — without
#     waiting for the rollover job to run.

#     Returns:
#         {
#             "casual_balance":   float,   # projected closing casual balance
#             "casual_used":      float,   # total casual days used from anchor month onwards
#             "comp_off_balance": float,   # projected closing comp_off balance
#             "comp_off_used":    float,   # total comp_off days used from anchor month onwards
#         }
#     """
#     today = date.today()

#     # ── Phase 1: Find the latest ledger row per leave type ────────────────────
#     result = await db.execute(
#         select(EmployeeLeaveBalance)
#         .where(EmployeeLeaveBalance.employee_id == employee_id)
#         .order_by(
#             EmployeeLeaveBalance.leave_type,
#             EmployeeLeaveBalance.year.desc(),
#             EmployeeLeaveBalance.month.desc(),
#         )
#     )
#     all_rows = result.scalars().all()

#     # Keep only the latest row per leave type
#     seen: set = set()
#     latest: dict[str, EmployeeLeaveBalance] = {}
#     for row in all_rows:
#         if row.leave_type not in seen:
#             seen.add(row.leave_type)
#             latest[row.leave_type] = row

#     casual_row = latest.get("casual")
#     comp_row = latest.get("comp_off")

#     # Determine the anchor: the month from which we need to simulate forward.
#     # If ledger row exists for the current month, anchor IS that month —
#     # but we still need to account for unapplied leaves within it.
#     if casual_row:
#         anchor_year, anchor_month = casual_row.year, casual_row.month
#     else:
#         # Brand-new employee: simulate from the month before today so the
#         # walk-forward loop creates today's month row.
#         if today.month == 1:
#             anchor_year, anchor_month = today.year - 1, 12
#         else:
#             anchor_year, anchor_month = today.year, today.month - 1

#     # Starting balances at the anchor (ledger closing, or 0 for new employee)
#     casual_closing = float(casual_row.closing_balance) if casual_row else 0.0
#     comp_closing = float(comp_row.closing_balance) if comp_row else 0.0

#     # How many days does the ledger already record as used in the anchor month?
#     # We need this so we don't double-count leave that the rollover already wrote.
#     casual_anchor_used = float(casual_row.used) if casual_row else 0.0
#     comp_anchor_used = float(comp_row.used) if comp_row else 0.0

#     # ── Phase 2: Fetch ALL approved leave requests from anchor month onwards ──

#     anchor_first, _ = _month_range(anchor_year, anchor_month)

#     # Use column-only select — avoids ORM lazy-load hangs on subsequent queries
#     leave_result = await db.execute(
#         select(
#             LeaveWFHRequest.from_date,
#             LeaveWFHRequest.to_date,
#             LeaveWFHRequest.organization_id,
#         ).where(
#             LeaveWFHRequest.employee_id == employee_id,
#             LeaveWFHRequest.request_type == "leave",
#             LeaveWFHRequest.status == "approved",
#             LeaveWFHRequest.to_date >= anchor_first,
#         )
#     )
#     leave_requests = leave_result.all()  # plain Row tuples

#     # Determine the furthest month we need to project up to.
#     end_year, end_month = today.year, today.month
#     for req in leave_requests:
#         ry, rm = req.to_date.year, req.to_date.month
#         if (ry, rm) > (end_year, end_month):
#             end_year, end_month = ry, rm

#     # Fetch org_id for holiday lookups (all requests share the same org)
#     org_id = leave_requests[0].organization_id if leave_requests else None

#     # ── Phase 3: Walk forward month by month from anchor to end ──────────────

#     # Accumulate totals for the response
#     total_casual_used = 0.0
#     total_comp_used = 0.0

#     # Check if we are already AT the anchor month (ledger current) vs need to walk
#     # We always iterate — even if start == end — to handle the "anchor = current month"
#     # case where the ledger may be stale within the month.

#     for year, month in _months_from_to(anchor_year, anchor_month, end_year, end_month):

#         # Has the rollover already written a row for this month?
#         ledger_row_casual = next(
#             (r for r in all_rows if r.leave_type == "casual" and r.year == year and r.month == month),
#             None,
#         )
#         ledger_row_comp = next(
#             (r for r in all_rows if r.leave_type == "comp_off" and r.year == year and r.month == month),
#             None,
#         )

#         # Apply accrual for this month (simulate what rollover would write)
#         if ledger_row_casual:
#             # Rollover already ran: use its closing as the new base BEFORE subtracting
#             # unapplied leaves (leaves approved after rollover ran this month).
#             casual_closing = float(ledger_row_casual.closing_balance)
#             already_used_casual = float(ledger_row_casual.used)
#         else:
#             # Rollover hasn't run yet: apply +1 accrual to the carry-forward closing
#             casual_closing += 1.0
#             already_used_casual = 0.0

#         if ledger_row_comp:
#             comp_closing = float(ledger_row_comp.closing_balance)
#             already_used_comp = float(ledger_row_comp.used)
#         else:
#             comp_closing = comp_closing   # no accrual for comp_off
#             already_used_comp = 0.0

#         # Count approved leave working days in this specific month
#         holiday_dates: set[date] = set()
#         if org_id:
#             holiday_dates = await _working_days_in_month(db, org_id, year, month)

#         month_first, month_last = _month_range(year, month)
#         month_leave_days = 0.0
#         for req in leave_requests:
#             if req.to_date < month_first:
#                 continue
#             if req.from_date > month_last:
#                 continue
#             month_leave_days += _count_working_days(
#                 req.from_date, req.to_date, year, month, holiday_dates
#             )

#         # Unapplied = total approved days this month - what rollover already recorded
#         unapplied_total = month_leave_days - already_used_casual - already_used_comp

#         if unapplied_total > 0:
#             # Apply comp_off-first priority on the UNAPPLIED portion
#             comp_available = comp_closing  # current comp balance before deduction
#             comp_unapplied = min(unapplied_total, max(0.0, comp_available))
#             casual_unapplied = unapplied_total - comp_unapplied

#             casual_closing -= casual_unapplied
#             comp_closing -= comp_unapplied

#             total_casual_used += casual_unapplied + already_used_casual
#             total_comp_used += comp_unapplied + already_used_comp
#         else:
#             total_casual_used += already_used_casual
#             total_comp_used += already_used_comp

#     # If anchor == end (no walk happened) but the anchor month itself has
#     # unapplied leave (leaves approved after rollover ran), handle that here.
#     if (anchor_year, anchor_month) == (end_year, end_month):
#         holiday_dates = set()
#         if org_id:
#             holiday_dates = await _working_days_in_month(db, org_id, anchor_year, anchor_month)

#         anchor_month_days = 0.0
#         anchor_first_day, anchor_last_day = _month_range(anchor_year, anchor_month)
#         for req in leave_requests:
#             if req.to_date < anchor_first_day or req.from_date > anchor_last_day:
#                 continue
#             anchor_month_days += _count_working_days(
#                 req.from_date, req.to_date, anchor_year, anchor_month, holiday_dates
#             )

#         unapplied_total = anchor_month_days - casual_anchor_used - comp_anchor_used
#         if unapplied_total > 0:
#             comp_available = comp_closing
#             comp_unapplied = min(unapplied_total, max(0.0, comp_available))
#             casual_unapplied = unapplied_total - comp_unapplied
#             casual_closing -= casual_unapplied
#             comp_closing -= comp_unapplied
#             total_casual_used += casual_unapplied
#             total_comp_used += comp_unapplied

#     return {
#         "casual_balance": casual_closing,
#         "casual_used": total_casual_used,
#         "comp_off_balance": comp_closing,
#         "comp_off_used": total_comp_used,
#     }


# async def get_balance_rows(db: AsyncSession, employee_id) -> list[EmployeeLeaveBalance]:
#     """
#     Return the single latest ledger row per leave type for the given employee.
#     Used by the /balances endpoint to show raw ledger data alongside real-time closing.
#     """
#     result = await db.execute(
#         select(EmployeeLeaveBalance)
#         .where(EmployeeLeaveBalance.employee_id == employee_id)
#         .order_by(
#             EmployeeLeaveBalance.leave_type,
#             EmployeeLeaveBalance.year.desc(),
#             EmployeeLeaveBalance.month.desc(),
#         )
#     )
#     rows = result.scalars().all()
#     seen: set = set()
#     latest = []
#     for row in rows:
#         if row.leave_type not in seen:
#             seen.add(row.leave_type)
#             latest.append(row)
#     return latest