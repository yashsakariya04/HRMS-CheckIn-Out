# app/routers/requests.py
"""
Request routes.

POST   /api/v1/requests                  - employee submits a request
GET    /api/v1/requests                  - employee views their own requests
GET    /api/v1/requests/all              - admin views all requests
PATCH  /api/v1/requests/{id}/approve     - admin approves a request
PATCH  /api/v1/requests/{id}/reject      - admin rejects a request
DELETE /api/v1/requests/{id}             - employee cancels a pending request
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.employee import Employee
from app.schemas.request_Emp import RequestCreate, RequestListResponse, RequestReject, RequestResponse
from app.services import request_service

router = APIRouter(prefix="/requests", tags=["Requests"])


@router.post("", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
def create_request(
    body: RequestCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Employee submits a new leave/wfh/missing_time/comp_off request."""
    return request_service.create_request(db, current_user, body)


@router.get("", response_model=List[RequestResponse])
def get_my_requests(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Returns all requests submitted by the logged-in employee, newest first."""
    return request_service.get_user_requests(db, current_user)


@router.get("/all", response_model=List[RequestListResponse])
def get_all_requests(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """Admin — returns all requests across the org with employee name and email."""
    return request_service.get_all_requests(db)


@router.patch("/{request_id}/approve", response_model=RequestResponse)
def approve_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """Admin approves a pending request and applies the correct side-effect."""
    return request_service.approve_request(db, request_id, current_user)


@router.patch("/{request_id}/reject", response_model=RequestResponse)
def reject_request(
    request_id: str,
    body: RequestReject = RequestReject(),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """Admin rejects a pending request with an optional note."""
    return request_service.reject_request(db, request_id, current_user, body.note)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Employee cancels their own pending request."""
    request_service.cancel_request(db, request_id, current_user)
