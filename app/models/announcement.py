"""
app/models/announcement.py — Announcement Database Model
=========================================================
Defines the `announcement` table.

Non-technical summary:
----------------------
Admins can post company-wide announcements.
Employees can see these announcements on their dashboard.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Announcement(Base):
    """ORM model for the `announcement` table."""
    __tablename__ = "announcement"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Title of the announcement
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Detailed body/content of the announcement
    content: Mapped[str] = mapped_column(String, nullable=False)

    # Who created the announcement (normally an admin)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"),
    )
