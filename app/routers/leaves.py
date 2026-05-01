"""
app/routers/leaves.py — Employee Leave History & Admin Summary Endpoints
========================================================================

GET /api/v1/leaves/me              — Employee views their own approved leave history.
GET /api/v1/leaves/{employee_id}   — Admin views any employee's approved leave history.
GET /api/v1/leaves/summary         — Admin views per-employee real-time balance summary.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
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

    Response shape:
      current_month   — individual leave dates (ISO strings) for this month.
      previous_months — per-month totals + dates for all prior months.
    """
    return await leave_service_Emp.get_my_leaves(db, current_user.id)


@router.get("/summary")
async def leave_summary(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: real-time leave balance summary for every employee.

    Returns each employee's casual and comp_off balance — same values
    the employee sees in /balances/me.  Balances include future-month
    approved leaves and are always up to date without waiting for the
    rollover job.
    """
    return await leave_service.get_leave_summary(db)


@router.get("/{employee_id}", response_model=LeavesResponse)
async def get_employee_leaves(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: return any employee's approved leave history.
    Same shape as /leaves/me but for a specified employee.
    """
    result = await leave_service_Emp.get_my_leaves(db, employee_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return result










