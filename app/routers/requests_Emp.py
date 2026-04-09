from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.employee import Employee
from app.schemas.request_Emp import RequestCreate, RequestListResponse, RequestReject, RequestResponse,LeaveSummaryRow
from app.services import request_service
from app.services.leave_service import get_leave_summary
router = APIRouter(prefix="/requests", tags=["Requests"])


@router.post("", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    body: RequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return await request_service.create_request(db, current_user, body)

@router.get("", response_model=List[RequestResponse])
async def get_my_requests(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return await request_service.get_user_requests(db, current_user)

@router.get("/requests")
async def list_requests(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """Return all leave / WFH requests for every employee. Admin only."""
    return await request_service.get_all_requests(db)



@router.patch("/{request_id}/approve", response_model=RequestResponse)
async def approve_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    return await request_service.approve_request(db, request_id, current_user)


@router.patch("/{request_id}/reject", response_model=RequestResponse)
async def reject_request(
    request_id: str,
    body: RequestReject = RequestReject(),
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    return await request_service.reject_request(db, request_id, current_user, body.note)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    await request_service.cancel_request(db, request_id, current_user)
