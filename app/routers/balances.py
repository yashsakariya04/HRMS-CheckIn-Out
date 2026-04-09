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
from app.services.balance_service import _get_current_month_balances
router = APIRouter(prefix="/balances", tags=["Leave Balances"])

@router.get("/me", response_model=List[BalanceResponse])
async def get_my_balances(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return await _get_current_month_balances(db, current_user.id)


# @router.get("/summary", response_model=List[dict])
# async def get_balances_summary(
#     db: AsyncSession = Depends(get_db),
#     current_user: Employee = Depends(require_admin),
# ):
#     today = date.today()
#     result = await db.execute(
#         select(EmployeeLeaveBalance).where(
#             EmployeeLeaveBalance.year == today.year,
#             EmployeeLeaveBalance.month == today.month,
#         )
#     )
#     rows = result.scalars().all()
#     return [
#         {
#             "employee_id": r.employee_id,
#             "leave_type": r.leave_type,
#             "closing_balance": float(r.closing_balance),
#             "used": float(r.used),
#         }
#         for r in rows
#     ]


@router.get("/{emp_id}", response_model=List[BalanceResponse])
async def get_employee_balances(
    emp_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    return await _get_current_month_balances(db, emp_id)
