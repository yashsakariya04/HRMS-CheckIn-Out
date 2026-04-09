"""
app/models/holiday.py — Holiday Database Model
===============================================
Defines the `holiday` table — the company holiday calendar.

Non-technical summary:
----------------------
Admins can add official holidays (e.g. Diwali, Christmas, company off-days).
These appear on the calendar so employees know which days are non-working.

Holiday types:
  - "national"  : Public/government holidays (e.g. Independence Day)
  - "regional"  : State/region-specific holidays
  - "optional"  : Employees can choose to take or skip
  - "company"   : Company-specific off-days (e.g. company anniversary)

Each organization can only have one holiday per date (no duplicates).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, TIMESTAMP, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Holiday(Base):
    """ORM model for the `holiday` table."""
    __tablename__ = "holiday"

    __table_args__ = (
        # One holiday per date per organization
        UniqueConstraint("organization_id", "holiday_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False,
    )

    # The actual date of the holiday
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Display name (e.g. "Diwali", "Christmas", "Company Offsite")
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Category: "national" | "regional" | "optional" | "company"
    holiday_type: Mapped[str] = mapped_column(
        String(30), server_default="national", nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
