"""
app/services/leave_service.py — Admin Leave Summary Service
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest as LeaveRequest
from app.services.balance_service import compute_realtime_balance


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
    # Get all employees who have at least one balance row
    result = await db.execute(
        select(Employee).join(
            EmployeeLeaveBalance, EmployeeLeaveBalance.employee_id == Employee.id
        ).distinct()
    )
    employees = result.scalars().all()

    output = []
    for emp in employees:
        balances = await compute_realtime_balance(db, emp.id)
        output.append({
            "employee_name": emp.full_name or str(emp.id),
            **balances,
        })
    return output
