"""
app/schemas/announcement.py — Announcement Validation Schemas
============================================================
Pydantic schemas for announcement endpoints.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    """Body for POST /announcements — admin adds a new announcement."""
    title: str = Field(..., max_length=255, description="Title of the announcement")
    content: str = Field(..., description="Main content/body of the announcement")


class AnnouncementUpdate(BaseModel):
    """Body for PATCH /announcements/{id} — admin edits an announcement."""
    title: str | None = Field(None, max_length=255, description="New title of the announcement")
    content: str | None = Field(None, description="New content/body of the announcement")


class AnnouncementResponse(BaseModel):
    """Response returned for announcements."""
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    content: str
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
