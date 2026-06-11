
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
from app.models.holiday import Holiday
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

    Optimized to avoid N+1 queries by bulk-fetching all data upfront.
    """
    from calendar import monthrange
    from datetime import date

    today = date.today()
    cur_year, cur_month = today.year, today.month
    first_day = date(cur_year, cur_month, 1)
    last_day = date(cur_year, cur_month, monthrange(cur_year, cur_month)[1])

    # ── 1. Fetch all employees with balance records ─────────────────────
    result = await db.execute(
        select(Employee.id, Employee.full_name, Employee.joined_on)
        .join(EmployeeLeaveBalance, EmployeeLeaveBalance.employee_id == Employee.id)
        .where(Employee.role != "superadmin")
        .distinct()
    )
    employees = result.all()
    if not employees:
        return []

    employee_ids = [emp.id for emp in employees]
    employees_map = {emp.id: emp.joined_on for emp in employees}

    # ── 2. Bulk-fetch all balance rows for these employees ────────────────
    balances_result = await db.execute(
        select(EmployeeLeaveBalance)
        .where(EmployeeLeaveBalance.employee_id.in_(employee_ids))
        .order_by(
            EmployeeLeaveBalance.employee_id,
            EmployeeLeaveBalance.leave_type,
            EmployeeLeaveBalance.year.desc(),
            EmployeeLeaveBalance.month.desc(),
        )
    )
    all_balances = balances_result.scalars().all()

    # Group by employee_id
    balances_by_employee = {}
    for balance in all_balances:
        if balance.employee_id not in balances_by_employee:
            balances_by_employee[balance.employee_id] = []
        balances_by_employee[balance.employee_id].append(balance)

    # ── 3. Bulk-fetch all current month leave requests ────────────────────
    leave_requests_result = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.employee_id.in_(employee_ids),
            LeaveRequest.request_type == "leave",
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= last_day,
            LeaveRequest.to_date >= first_day,
        )
    )
    all_leave_requests = leave_requests_result.scalars().all()

    # Group by employee_id
    leave_requests_by_employee = {}
    org_id = None
    for req in all_leave_requests:
        if req.employee_id not in leave_requests_by_employee:
            leave_requests_by_employee[req.employee_id] = []
        leave_requests_by_employee[req.employee_id].append(req)
        if org_id is None:
            org_id = req.organization_id

    # ── 4. Bulk-fetch holidays for current month ─────────────────────────
    holiday_dates = set()
    if org_id:
        holidays_result = await db.execute(
            select(Holiday.holiday_date).where(
                Holiday.organization_id == org_id,
                Holiday.holiday_date >= first_day,
                Holiday.holiday_date <= last_day,
            )
        )
        holiday_dates = set(holidays_result.scalars().all())

    # ── 5. Build bulk_data dict and compute balances ─────────────────────
    bulk_data = {
        'balances': balances_by_employee,
        'employees': employees_map,
        'leave_requests': leave_requests_by_employee,
        'holidays': holiday_dates,
    }

    output = []
    for emp in employees:
        balances = await compute_realtime_balance(db, emp.id, bulk_data)
        output.append({
            "employee_id": str(emp.id),
            "employee_name": emp.full_name or str(emp.id),
            **balances,
        })
    return output