"""
app/services/announcement_service.py — Announcement Management Business Logic
=============================================================================
Handles creating, listing, updating, and deleting announcements.
"""

from datetime import datetime
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate


async def create_announcement(
    data: AnnouncementCreate, db, employee_id: UUID, organization_id: UUID
) -> Announcement:
    """
    Create a new announcement for the organization.
    """
    announcement = Announcement(
        organization_id=organization_id,
        title=data.title,
        content=data.content,
        created_by=employee_id,
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)
    return announcement


async def get_announcements(db, organization_id: UUID) -> list[Announcement]:
    """
    Get all announcements for the organization sorted by creation date descending.
    """
    result = await db.execute(
        select(Announcement)
        .where(Announcement.organization_id == organization_id)
        .order_by(Announcement.created_at.desc())
    )
    return list(result.scalars().all())


async def get_announcement_by_id(
    announcement_id: UUID, db, organization_id: UUID
) -> Announcement:
    """
    Retrieve an announcement by its ID.
    """
    result = await db.execute(
        select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.organization_id == organization_id,
        )
    )
    announcement = result.scalars().first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return announcement


async def update_announcement(
    announcement_id: UUID, data: AnnouncementUpdate, db, organization_id: UUID
) -> Announcement:
    """
    Update an announcement.
    """
    announcement = await get_announcement_by_id(announcement_id, db, organization_id)
    if data.title is not None:
        announcement.title = data.title
    if data.content is not None:
        announcement.content = data.content
    
    announcement.updated_at = datetime.now()
    await db.commit()
    await db.refresh(announcement)
    return announcement


async def delete_announcement(
    announcement_id: UUID, db, organization_id: UUID
) -> dict:
    """
    Permanently delete an announcement.
    """
    announcement = await get_announcement_by_id(announcement_id, db, organization_id)
    await db.delete(announcement)
    await db.commit()
    return {"message": "Announcement deleted successfully"}
