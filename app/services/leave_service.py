from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest as LeaveRequest


async def _get_employee_name(employee_id: UUID, db: AsyncSession) -> str:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalars().first()
    return emp.full_name if emp and emp.full_name else str(employee_id)


async def get_all_requests(db: AsyncSession) -> list[dict]:
    """Return every leave / WFH request across all employees, newest first."""
    result = await db.execute(
        select(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    )
    rows = []
    for req in result.scalars().all():
        rows.append({
            "id": req.id,
            "employee_name": await _get_employee_name(req.employee_id, db),
            "request_type": req.request_type,
            "from_date": req.from_date,
            "to_date": req.to_date,
            "reason": req.reason,
            "status": req.status,
        })
    return rows


async def get_leave_summary(db: AsyncSession) -> list[dict]:
    """
    For every employee, return their casual and comp_off balances
    for the current month, read directly from employee_leave_balance.
    """
    today = date.today()

    result = await db.execute(
        select(EmployeeLeaveBalance).where(
            EmployeeLeaveBalance.year == today.year,
            EmployeeLeaveBalance.month == today.month,
        )
    )
    balance_rows = result.scalars().all()

    # Group by employee
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
