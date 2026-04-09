from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user,require_admin
from app.models.employee import Employee
from app.schemas.leaves import LeavesResponse
from app.schemas.request_Emp import RequestListResponse,LeaveSummaryRow
from app.services import leave_service 
from app.services import leave_service_Emp
router = APIRouter(prefix="/leaves", tags=["Leaves"])


@router.get("/me", response_model=LeavesResponse)
async def get_my_leaves(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return await leave_service_Emp.get_my_leaves(db, current_user.id)


# @router.get("/all", response_model=List[LeaveSummaryRow])
# async def get_all_requests(
#     db: AsyncSession = Depends(get_db),
#     current_user: Employee = Depends(require_admin),
# ):
#     return await leave_service.get_leave_summary(db)

@router.get("/summary")
async def leave_summary(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Per-employee leave summary:
    this month's count, previous months breakdown, and remaining balance.
    Admin only.
    """
    return await leave_service.get_leave_summary(db)
