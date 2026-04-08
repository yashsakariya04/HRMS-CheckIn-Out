# app/routers/leaves.py
"""
Leaves routes.

GET /api/v1/leaves/me  - current user's leave history
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.employee import Employee
from app.schemas.leaves import LeavesResponse
from app.services import leave_service_Emp as leaves_service

router = APIRouter(prefix="/leaves", tags=["Leaves"])


@router.get("/me", response_model=LeavesResponse)
def get_my_leaves(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Returns the current user's approved leave history.
    Splits into current month dates and previous months grouped summary.
    """
    return leaves_service.get_my_leaves(db, current_user.id)
