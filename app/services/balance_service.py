"""
app/services/balance_service.py — Leave Balance Query Service
=============================================================
Provides helper functions for fetching leave balance records.

Non-technical summary:
----------------------
This service retrieves an employee's leave balance rows for the
current calendar month. It is used by both the employee-facing
balance endpoint (/balances/me) and the admin endpoint (/balances/{id}).
"""

from datetime import date
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_leave_balance import EmployeeLeaveBalance


async def _get_current_month_balances(
    db: AsyncSession, employee_id
) -> List[EmployeeLeaveBalance]:
    """
    Return all leave balance rows for the given employee for the current month.

    Returns one row per leave type (e.g. casual, comp_off).
    Returns an empty list if no balance rows exist yet for this month
    (the rollover job may not have run yet).

    Args:
        db:          Async database session.
        employee_id: UUID of the employee (as string or UUID object).

    Returns:
        List of EmployeeLeaveBalance ORM objects for the current month.
    """
    today = date.today()
    result = await db.execute(
        select(EmployeeLeaveBalance).where(
            EmployeeLeaveBalance.employee_id == employee_id,
            EmployeeLeaveBalance.year == today.year,
            EmployeeLeaveBalance.month == today.month,
        )
    )
    return result.scalars().all()
