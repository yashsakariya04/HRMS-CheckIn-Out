"""
app/models/attendance_session.py — Attendance Session Database Model
====================================================================
Defines the `attendance_session` table — one row per employee per working day.

Non-technical summary:
----------------------
Every time an employee checks in, a new row is created here.
When they check out, the same row is updated with the checkout time
and total hours worked.

Rules enforced at the database level:
  - Only ONE session per employee per day (UniqueConstraint).
  - Checkout time must be AFTER check-in time (CheckConstraint).

Key fields:
  - check_out_at = NULL  → employee is still checked in (session is open)
  - total_hours          → calculated on checkout (e.g. 8.5 = 8h 30m)
  - work_mode            → "office", "wfh", or "client_site"
  - is_corrected         → True if a missing_time request was approved
                           and the checkout was filled in by an admin

Each session can have multiple TaskEntry records linked to it.
"""

import uuid
from datetime import date, datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey,
    Index, Numeric, String, TIMESTAMP, text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class AttendanceSession(Base):
    """ORM model for the `attendance_session` table."""
    __tablename__ = "attendance_session"

    __table_args__ = (
        # One session per employee per day
        UniqueConstraint("employee_id", "session_date", name="uq_session_per_day"),
        # Checkout must be after check-in (NULL checkout = still open, allowed)
        CheckConstraint(
            "check_out_at IS NULL OR check_out_at > check_in_at",
            name="chk_checkout_after_checkin",
        ),
        # Indexes for fast queries by employee+date and org+date
        Index("idx_sess_emp_date", "employee_id", "session_date"),
        Index("idx_sess_org_date", "organization_id", "session_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False,
    )

    # The calendar date of this work session (not a timestamp)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Exact UTC timestamp when the employee checked in
    check_in_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
    )

    # NULL = session still open. Filled on checkout.
    check_out_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # Decimal hours worked, e.g. 8.5 = 8 hours 30 minutes. NULL until checkout.
    total_hours: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Where the employee worked: "office" | "wfh" | "client_site"
    work_mode: Mapped[str] = mapped_column(
        String(20), server_default="office", nullable=False,
    )

    # True when an admin approved a missing_time request and corrected checkout
    is_corrected: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False,
    )

    # Admin note explaining why the session was corrected (optional)
    correction_note: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )

    # All task entries logged during this session (loaded automatically)
    tasks: Mapped[List["TaskEntry"]] = relationship(
        "TaskEntry", lazy="selectin", cascade="all, delete-orphan",
    )
