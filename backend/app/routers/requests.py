# api/leave_request_api.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from backend.app.schemas.request import ReviewRequestBody
from backend.app.services.leave_service import (
    get_all_requests,
    approve_request,
    reject_request,
    get_leave_summary,
)
from backend.app.dependencies.database import get_db
from backend.app.dependencies.auth import require_admin

router = APIRouter(prefix="/leave", tags=["Leave & WFH"])


# ── TAB 1: Requests ───────────────────────────────────────────────────────────

@router.get("/requests")
async def list_requests(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Return all leave / WFH requests for every employee.
    Admin only.
    """
    return await get_all_requests(db)


@router.patch("/requests/{request_id}/approve")
async def approve(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Approve a pending leave / WFH request.
    Admin only.
    """
    return await approve_request(request_id, admin.id, db)


@router.patch("/requests/{request_id}/reject")
async def reject(
    request_id: UUID,
    data: ReviewRequestBody,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Reject a pending leave / WFH request with an optional note.
    Admin only.
    """
    return await reject_request(request_id, admin.id, data.rejection_note, db)


# ── TAB 2: Leave Summary ──────────────────────────────────────────────────────

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
    return await get_leave_summary(db)