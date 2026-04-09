"""
app/routers/requests_Emp.py — Leave/WFH Request API Endpoints
=============================================================
Handles employee request submission and admin approval/rejection.

Endpoints:
  POST   /api/v1/requests                      — Employee submits a new request
  GET    /api/v1/requests                      — Employee views their own requests
  GET    /api/v1/requests/requests             — Admin views ALL requests (all employees)
  PATCH  /api/v1/requests/{id}/approve         — Admin approves a request
  PATCH  /api/v1/requests/{id}/reject          — Admin rejects a request
  DELETE /api/v1/requests/{id}                 — Employee cancels a pending request
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.request_Emp import (
    RequestCreate, RequestListResponse, RequestReject, RequestResponse,
)
from app.services import request_service

router = APIRouter(prefix="/requests", tags=["Requests"])


@router.post("", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    body: RequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Employee submits a new leave, WFH, missing-time, or comp-off request.
    The request starts with status = "pending".
    """
    return await request_service.create_request(db, current_user, body)


@router.get("", response_model=List[RequestResponse])
async def get_my_requests(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Return all requests submitted by the currently logged-in employee."""
    return await request_service.get_user_requests(db, current_user)


@router.get("/requests")
async def list_requests(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: return all leave/WFH requests from every employee.
    Includes employee name and email for each request.
    """
    return await request_service.get_all_requests(db)


@router.patch("/{request_id}/approve", response_model=RequestResponse)
async def approve_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """
    Admin only: approve a pending request.
    Triggers side effects based on request type:
      - leave       → deducts from leave balance (comp_off first, then casual)
      - wfh         → marks attendance session work_mode = "wfh"
      - missing_time → fills in checkout time on the linked session
      - comp_off    → credits +1 to comp_off balance
    """
    return await request_service.approve_request(db, request_id, current_user)


@router.patch("/{request_id}/reject", response_model=RequestResponse)
async def reject_request(
    request_id: str,
    body: RequestReject = RequestReject(),
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """
    Admin only: reject a pending request with an optional note.
    No balance or session changes are made on rejection.
    """
    return await request_service.reject_request(db, request_id, current_user, body.note)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Employee cancels their own pending request.
    Only the request owner can cancel, and only while status is "pending".
    """
    await request_service.cancel_request(db, request_id, current_user)
