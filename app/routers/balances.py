"""
app/routers/balances.py — Leave Balance API Endpoints
======================================================
Endpoints for querying leave balances.

Endpoints:
  GET /api/v1/balances/me          — Employee views their own current month balances
  GET /api/v1/balances/{emp_id}    — Admin views any employee's current month balances
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.attendance import BalanceResponse
from app.services.balance_service import compute_realtime_balance, get_balance_rows

router = APIRouter(prefix="/balances", tags=["Leave Balances"])


async def _build_balance_response(db, employee_id) -> List[dict]:
    """
    Returns balance rows with closing_balance replaced by real-time value.
    Keeps the same list-of-rows shape the frontend expects.
    """
    rows = await get_balance_rows(db, employee_id)
    realtime = await compute_realtime_balance(db, employee_id)

    result = []
    for row in rows:
        d = {
            "leave_type": row.leave_type,
            "year": row.year,
            "month": row.month,
            "opening_balance": float(row.opening_balance),
            "accrued": float(row.accrued),
            "used": float(row.used),
            "adjusted": float(row.adjusted),
            "closing_balance": (
                realtime["casual_balance"] if row.leave_type == "casual"
                else realtime["comp_off_balance"]
            ),
        }
        result.append(d)
    return result


@router.get("/me")
async def get_my_balances(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return await _build_balance_response(db, current_user.id)


@router.get("/{emp_id}")
async def get_employee_balances(
    emp_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    return await _build_balance_response(db, emp_id)
