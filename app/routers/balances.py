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
from app.services.balance_service import _get_current_month_balances

router = APIRouter(prefix="/balances", tags=["Leave Balances"])


@router.get("/me", response_model=List[BalanceResponse])
async def get_my_balances(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Return the logged-in employee's leave balances for the current month.
    Returns one row per leave type (casual, comp_off).
    """
    return await _get_current_month_balances(db, current_user.id)


@router.get("/{emp_id}", response_model=List[BalanceResponse])
async def get_employee_balances(
    emp_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """
    Admin only: return leave balances for any employee by their ID.
    Returns current month balances for all leave types.
    """
    return await _get_current_month_balances(db, emp_id)
