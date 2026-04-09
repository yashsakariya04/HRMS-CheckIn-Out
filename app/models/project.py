"""
app/models/project.py — Project Database Model
===============================================
Defines the `project` table — projects that employees log tasks against.

Non-technical summary:
----------------------
When an employee checks in and logs their work, they must assign each
task to a project. This table stores the list of available projects.

Projects are soft-deleted (is_active = False) rather than hard-deleted,
so historical task entries that reference old projects are preserved.
Project names must be unique within the same organization.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, TIMESTAMP, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Project(Base):
    """ORM model for the `project` table."""
    __tablename__ = "project"

    __table_args__ = (
        # Two projects in the same org cannot share the same name
        UniqueConstraint("organization_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Project display name (e.g. "Website Redesign", "Internal Tools")
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional longer description of the project
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    # False = soft-deleted. Inactive projects don't appear in dropdowns
    # but their historical task entries are preserved.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"),
    )
