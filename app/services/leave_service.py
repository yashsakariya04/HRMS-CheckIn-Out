# """
# app/services/leave_service.py — Admin Leave Summary Service
# """

# from uuid import UUID

# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.employee import Employee
# from app.models.employee_leave_balance import EmployeeLeaveBalance
# from app.models.leave_wfh_request import LeaveWFHRequest as LeaveRequest
# from app.services.balance_service import compute_realtime_balance


# async def get_all_requests(db: AsyncSession) -> list[dict]:
#     result = await db.execute(
#         select(LeaveRequest, Employee)
#         .join(Employee, Employee.id == LeaveRequest.employee_id)
#         .order_by(LeaveRequest.created_at.desc())
#     )
#     return [
#         {
#             "id": req.id,
#             "employee_name": emp.full_name or str(emp.id),
#             "request_type": req.request_type,
#             "from_date": req.from_date,
#             "to_date": req.to_date,
#             "reason": req.reason,
#             "status": req.status,
#             "created_at": req.created_at,
#         }
#         for req, emp in result.all()
#     ]


# async def get_leave_summary(db: AsyncSession) -> list[dict]:
#     # Get all employees who have at least one balance row
#     result = await db.execute(
#         select(Employee).join(
#             EmployeeLeaveBalance, EmployeeLeaveBalance.employee_id == Employee.id
#         ).distinct()
#     )
#     employees = result.scalars().all()

#     output = []
#     for emp in employees:
#         balances = await compute_realtime_balance(db, emp.id)
#         output.append({
#             "employee_name": emp.full_name or str(emp.id),
#             **balances,
#         })
#     return output




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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest as LeaveRequest
from app.services.balance_service import compute_realtime_balance


async def get_all_requests(db: AsyncSession) -> list[dict]:
    """
    Return every leave/WFH request across all employees, newest first.
    """
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
    Return a real-time leave balance summary for every employee who has at
    least one balance ledger row.
    """
    # Fetch only the columns we need — no ORM object, no lazy-load risk
    result = await db.execute(
        select(Employee.id, Employee.full_name)
        .join(EmployeeLeaveBalance, EmployeeLeaveBalance.employee_id == Employee.id)
        .distinct()
    )
    employees = result.all()  # plain Row tuples (id, full_name)

    output = []
    for emp in employees:
        balances = await compute_realtime_balance(db, emp.id)
        output.append({
            "employee_id": str(emp.id),
            "employee_name": emp.full_name or str(emp.id),
            **balances,
        })
    return output