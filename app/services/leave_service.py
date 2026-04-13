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

from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest as LeaveRequest


async def _get_employee_name(employee_id: UUID, db: AsyncSession) -> str:
    """
    Helper: return the employee's full name, or their UUID string as fallback.

    Args:
        employee_id: UUID of the employee.
        db:          Async database session.
    """
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalars().first()
    return emp.full_name if emp and emp.full_name else str(employee_id)


async def get_all_requests(db: AsyncSession) -> list[dict]:
    """
    Return every leave/WFH request across all employees, newest first.

    Used by the admin panel to review and act on pending requests.

    Returns:
        List of dicts with request details and the employee's name.
    """
    result = await db.execute(
        select(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    )
    rows = [
        {
            "id": req.id,
            "employee_name": await _get_employee_name(req.employee_id, db),
            "request_type": req.request_type,
            "from_date": req.from_date,
            "to_date": req.to_date,
            "reason": req.reason,
            "status": req.status,
        }
        for req in result.scalars().all()
    ]
    return rows


async def get_leave_summary(db: AsyncSession) -> list[dict]:
    """
    Return per-employee casual and comp_off leave balances for the current month.

    Reads directly from employee_leave_balance for the current year/month.
    Groups rows by employee and extracts casual and comp_off balances.

    Returns:
        List of dicts, one per employee, with balance and usage figures.
    """
    today = date.today()

    result = await db.execute(
        select(EmployeeLeaveBalance).where(
            EmployeeLeaveBalance.year == today.year,
            EmployeeLeaveBalance.month == today.month,
        )
    )
    balance_rows = result.scalars().all()

    # Group balance rows by employee ID
    by_employee: dict[UUID, dict] = {}
    for row in balance_rows:
        emp_id = row.employee_id
        if emp_id not in by_employee:
            by_employee[emp_id] = {"casual": None, "comp_off": None}
        if row.leave_type in ("casual", "comp_off"):
            by_employee[emp_id][row.leave_type] = row

    rows = []
    for emp_id, balances in by_employee.items():
        casual = balances["casual"]
        comp = balances["comp_off"]
        rows.append({
            "employee_name": await _get_employee_name(emp_id, db),
            "casual_balance": float(casual.closing_balance or 0) if casual else 0.0,
            "casual_used": float(casual.used) if casual else 0.0,
            "comp_off_balance": float(comp.closing_balance or 0) if comp else 0.0,
            "comp_off_used": float(comp.used) if comp else 0.0,
        })
    return rows
