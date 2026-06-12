"""
app/routers/announcement_api.py — Announcement API Endpoints
============================================================
Provides routes for creating, listing, updating, and deleting announcements.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse
from app.services.announcement_service import (
    create_announcement,
    delete_announcement,
    get_announcements,
    get_announcement_by_id,
    update_announcement,
)

router = APIRouter(prefix="/announcements", tags=["Announcements"])


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def add_announcement(
    data: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    """
    Admin only: Create a new company announcement.
    """
    return await create_announcement(
        data=data,
        db=db,
        employee_id=admin.id,
        organization_id=admin.organization_id,
    )


@router.get("", response_model=list[AnnouncementResponse])
async def list_announcements(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Get all announcements for the logged-in user's organization.
    """
    return await get_announcements(db=db, organization_id=current_user.organization_id)


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def retrieve_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Get details of a specific announcement by its ID.
    """
    return await get_announcement_by_id(
        announcement_id=announcement_id,
        db=db,
        organization_id=current_user.organization_id,
    )


@router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def edit_announcement(
    announcement_id: UUID,
    data: AnnouncementUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    """
    Admin only: Edit/update an existing announcement.
    """
    return await update_announcement(
        announcement_id=announcement_id,
        data=data,
        db=db,
        organization_id=admin.organization_id,
    )


@router.delete("/{announcement_id}", status_code=status.HTTP_200_OK)
async def remove_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    """
    Admin only: Permanently delete an announcement.
    """
    return await delete_announcement(
        announcement_id=announcement_id,
        db=db,
        organization_id=admin.organization_id,
    )
