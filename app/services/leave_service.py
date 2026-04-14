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
                      balance for the current month — how much they
                      have left and how much they've used.
"""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest as LeaveRequest


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
        }
        for req, emp in result.all()
    ]


async def get_leave_summary(db: AsyncSession) -> list[dict]:
    today = date.today()

    result = await db.execute(
        select(EmployeeLeaveBalance, Employee)
        .join(Employee, Employee.id == EmployeeLeaveBalance.employee_id)
        .where(
            EmployeeLeaveBalance.year == today.year,
            EmployeeLeaveBalance.month == today.month,
        )
    )
    rows = result.all()

    by_employee: dict[UUID, dict] = {}
    for balance_row, emp in rows:
        emp_id = balance_row.employee_id
        if emp_id not in by_employee:
            by_employee[emp_id] = {"name": emp.full_name or str(emp_id), "casual": None, "comp_off": None}
        if balance_row.leave_type in ("casual", "comp_off"):
            by_employee[emp_id][balance_row.leave_type] = balance_row

    output = []
    for emp_id, data in by_employee.items():
        casual = data["casual"]
        comp = data["comp_off"]
        output.append({
            "employee_name": data["name"],
            "casual_balance": float(casual.closing_balance or 0) if casual else 0.0,
            "casual_used": float(casual.used) if casual else 0.0,
            "comp_off_balance": float(comp.closing_balance or 0) if comp else 0.0,
            "comp_off_used": float(comp.used) if comp else 0.0,
        })
    return output
