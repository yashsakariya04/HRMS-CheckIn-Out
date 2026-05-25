
"""
app/services/leave_service.py — Admin Leave Summary Service
===========================================================
Provides admin-facing data:
  • get_all_requests() — all leave/WFH/comp-off/missing-time requests with
                         employee name & email.
  • get_leave_summary() — per-employee real-time leave balance summary.

Both functions delegate balance computation to balance_service so the
figures shown to admins are always identical to what employees see.
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.holiday import Holiday
from app.models.leave_wfh_request import LeaveWFHRequest as LeaveRequest
from app.jobs.leave_rollover import _is_in_probation


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


async def get_all_requests(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(
            LeaveRequest.id,
            LeaveRequest.request_type,
            LeaveRequest.from_date,
            LeaveRequest.to_date,
            LeaveRequest.reason,
            LeaveRequest.status,
            LeaveRequest.rejection_note,
            LeaveRequest.reviewed_at,
            LeaveRequest.created_at,
            Employee.id.label("emp_id"),
            Employee.full_name,
            Employee.email,
        )
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .order_by(LeaveRequest.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(r.id),
            "employee_id": str(r.emp_id),
            "employee_name": r.full_name or str(r.emp_id),
            "employee_email": r.email,
            "request_type": r.request_type,
            "from_date": r.from_date,
            "to_date": r.to_date,
            "reason": r.reason,
            "status": r.status,
            "rejection_note": r.rejection_note,
            "reviewed_at": r.reviewed_at,
            "created_at": r.created_at,
        }
        for r in rows
    ]


async def get_leave_summary(db: AsyncSession) -> list[dict]:
    """
    Return a real-time leave balance summary for every employee.
    Uses 3 bulk queries instead of N×3 per-employee queries.
    """
    today = date.today()
    cur_year, cur_month = today.year, today.month
    first_day = date(cur_year, cur_month, 1)
    last_day = date(cur_year, cur_month, monthrange(cur_year, cur_month)[1])

    # ── 3 bulk queries (sequential — SQLAlchemy AsyncSession does not allow concurrent queries on the same session) ──
    emp_result = await db.execute(
        select(Employee.id, Employee.full_name, Employee.joined_on)
        .join(EmployeeLeaveBalance, EmployeeLeaveBalance.employee_id == Employee.id)
        .where(Employee.role != "superadmin")
        .distinct()
    )
    ledger_result = await db.execute(
        select(EmployeeLeaveBalance)
        .join(Employee, Employee.id == EmployeeLeaveBalance.employee_id)
        .where(Employee.role != "superadmin")
        .order_by(
            EmployeeLeaveBalance.employee_id,
            EmployeeLeaveBalance.leave_type,
            EmployeeLeaveBalance.year.desc(),
            EmployeeLeaveBalance.month.desc(),
        )
    )
    leave_result = await db.execute(
        select(LeaveRequest)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .where(
            Employee.role != "superadmin",
            LeaveRequest.request_type == "leave",
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= last_day,
            LeaveRequest.to_date >= first_day,
        )
    )

    employees = emp_result.all()
    if not employees:
        return []

    emp_ids = {emp.id for emp in employees}

    # Build latest ledger row per (employee_id, leave_type)
    seen: set = set()
    latest_ledger: dict[tuple, EmployeeLeaveBalance] = {}
    for row in ledger_result.scalars().all():
        key = (row.employee_id, row.leave_type)
        if key not in seen:
            seen.add(key)
            latest_ledger[key] = row

    # Group leave requests by employee
    leave_by_emp: dict = defaultdict(list)
    org_id = None
    for req in leave_result.scalars().all():
        if req.employee_id in emp_ids:
            leave_by_emp[req.employee_id].append(req)
            if org_id is None:
                org_id = req.organization_id

    # Fetch holidays once for the current month
    holiday_dates: set[date] = set()
    if org_id:
        h_result = await db.execute(
            select(Holiday.holiday_date).where(
                Holiday.organization_id == org_id,
                Holiday.holiday_date >= first_day,
                Holiday.holiday_date <= last_day,
            )
        )
        holiday_dates = set(h_result.scalars().all())

    # ── Compute balance per employee in Python ──────────────────────────
    output = []
    for emp in employees:
        casual_row = latest_ledger.get((emp.id, "casual"))
        comp_row   = latest_ledger.get((emp.id, "comp_off"))

        in_probation = _is_in_probation(emp.joined_on, cur_year, cur_month)
        simulated_accrual = 0.0 if in_probation else 1.0

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

        current_month_used = 0.0
        for req in leave_by_emp.get(emp.id, []):
            current = max(req.from_date, first_day)
            end = min(req.to_date, last_day)
            while current <= end:
                if not _is_weekend(current) and current not in holiday_dates:
                    current_month_used += 1
                current += timedelta(days=1)

        comp_off_available = max(0.0, comp_base)
        comp_off_unapplied = min(current_month_used, comp_off_available) - comp_already_used
        casual_unapplied = (current_month_used - min(current_month_used, comp_off_available)) - casual_already_used

        output.append({
            "employee_id": str(emp.id),
            "employee_name": emp.full_name or str(emp.id),
            "casual_balance": casual_base - casual_unapplied,
            "casual_used": current_month_used,
            "comp_off_balance": comp_base - comp_off_unapplied,
            "comp_off_used": comp_already_used + comp_off_unapplied,
        })

    return output