"""
app/services/leave_service.py — Admin Leave Summary Service
============================================================
Provides admin-facing leave data: all requests and per-employee
leave balance summaries.

Non-technical summary:
----------------------
Admins use this service to get a bird's-eye view of leave across
all employees. Two main functions:

  get_all_requests  : Returns every leave/WFH request ever submitted,
                      with the employee's name attached.

  get_leave_summary : Returns each employee's casual and comp_off
                      balance — latest ledger closing minus any future
                      approved leave days not yet rolled over.
"""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.holiday import Holiday
from app.models.leave_wfh_request import LeaveWFHRequest as LeaveRequest


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


async def get_all_requests(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(LeaveRequest, Employee)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .order_by(LeaveRequest.created_at.desc())
    )
    return [
        {
            "id": req.id,
            "employee_name": emp.full_name or str(emp.id),
            "request_type": req.request_type,
            "from_date": req.from_date,
            "to_date": req.to_date,
            "reason": req.reason,
            "status": req.status,
            "created_at": req.created_at,
        }
        for req, emp in result.all()
    ]


async def get_leave_summary(db: AsyncSession) -> list[dict]:
    # ── 1. Latest ledger row per employee per leave type ──────────────
    result = await db.execute(
        select(EmployeeLeaveBalance, Employee)
        .join(Employee, Employee.id == EmployeeLeaveBalance.employee_id)
        .order_by(
            EmployeeLeaveBalance.employee_id,
            EmployeeLeaveBalance.leave_type,
            EmployeeLeaveBalance.year.desc(),
            EmployeeLeaveBalance.month.desc(),
        )
    )
    rows = result.all()

    by_employee: dict[UUID, dict] = {}
    seen: dict[UUID, set] = {}
    for balance_row, emp in rows:
        emp_id = balance_row.employee_id
        if emp_id not in by_employee:
            by_employee[emp_id] = {"name": emp.full_name or str(emp_id), "casual": None, "comp_off": None}
            seen[emp_id] = set()
        if balance_row.leave_type in ("casual", "comp_off") and balance_row.leave_type not in seen[emp_id]:
            seen[emp_id].add(balance_row.leave_type)
            by_employee[emp_id][balance_row.leave_type] = balance_row

    # ── 2. Compute unapplied approved leave days per employee ──────────
    all_leave_result = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.request_type == "leave",
            LeaveRequest.status == "approved",
        )
    )
    all_leave_requests = all_leave_result.scalars().all()

    future_days_by_emp: dict[UUID, int] = {}
    for emp_id, data in by_employee.items():
        casual_row = data["casual"]
        emp_requests = [r for r in all_leave_requests if r.employee_id == emp_id]
        if not emp_requests or not casual_row:
            future_days_by_emp[emp_id] = 0
            continue

        org_id = emp_requests[0].organization_id
        min_date = min(r.from_date for r in emp_requests)
        max_date = max(r.to_date for r in emp_requests)
        holiday_result = await db.execute(
            select(Holiday.holiday_date).where(
                Holiday.organization_id == org_id,
                Holiday.holiday_date >= min_date,
                Holiday.holiday_date <= max_date,
            )
        )
        holiday_dates = {row for row in holiday_result.scalars().all()}

        total_approved_days = 0
        for req in emp_requests:
            current = req.from_date
            while current <= req.to_date:
                if not _is_weekend(current) and current not in holiday_dates:
                    total_approved_days += 1
                current += timedelta(days=1)

        already_in_ledger = float(casual_row.used)
        future_days_by_emp[emp_id] = total_approved_days - already_in_ledger

    # ── 3. Build output with virtual balance ──────────────────────────
    output = []
    for emp_id, data in by_employee.items():
        casual = data["casual"]
        comp = data["comp_off"]
        future_days = future_days_by_emp.get(emp_id, 0)
        casual_balance = float(casual.closing_balance or 0) - future_days if casual else 0.0
        output.append({
            "employee_name": data["name"],
            "casual_balance": casual_balance,
            "casual_used": float(casual.used) if casual else 0.0,
            "comp_off_balance": float(comp.closing_balance or 0) if comp else 0.0,
            "comp_off_used": float(comp.used) if comp else 0.0,
        })
    return output
