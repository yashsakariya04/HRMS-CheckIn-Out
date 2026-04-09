"""
app/schemas/add_project.py — Project Management Schemas
=======================================================
Pydantic schemas for admin endpoints that create and list projects.

Non-technical summary:
----------------------
Projects are what employees assign their daily tasks to.
Admins create and manage the list of available projects.

  - ProjectCreate   : Data needed to create a new project
  - ProjectResponse : Full project details returned by the API
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    """Body for POST /project/add — admin creates a new project."""
    name: str                        # Project display name (must be unique in the org)
    description: Optional[str] = None  # Optional longer description


class ProjectResponse(BaseModel):
    """Full project details returned by GET /project/ and POST /project/add."""
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool       # False = soft-deleted, won't appear in dropdowns
    created_at: datetime

    class Config:
        from_attributes = True
