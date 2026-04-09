from datetime import date
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.schemas.attendance import BalanceResponse


async def _get_current_month_balances(db: AsyncSession, employee_id) -> List[EmployeeLeaveBalance]:
    today = date.today()
    result = await db.execute(
        select(EmployeeLeaveBalance).where(
            EmployeeLeaveBalance.employee_id == employee_id,
            EmployeeLeaveBalance.year == today.year,
            EmployeeLeaveBalance.month == today.month,
        )
    )
    return result.scalars().all()