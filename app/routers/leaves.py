"""
app/routers/leaves.py — Employee Leave History Endpoints
=========================================================
Endpoints for viewing leave history and admin leave summaries.

Endpoints:
  GET /api/v1/leaves/me      — Employee views their own approved leave history
  GET /api/v1/leaves/summary — Admin views leave balance summary for all employees
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.leaves import LeavesResponse
from app.services import leave_service, leave_service_Emp

router = APIRouter(prefix="/leaves", tags=["Leaves"])


@router.get("/me", response_model=LeavesResponse)
async def get_my_leaves(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Return the logged-in employee's approved leave history.

    Response includes:
      - current_month : Individual leave dates this month
      - previous_months : Monthly totals for all past months
    """
    return await leave_service_Emp.get_my_leaves(db, current_user.id)


@router.get("/summary")
async def leave_summary(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: per-employee leave balance summary for the current month.

    Returns each employee's casual and comp_off balance, including
    how much has been used and how much remains.
    """
    return await leave_service.get_leave_summary(db)
