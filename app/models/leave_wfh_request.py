"""
app/models/leave_wfh_request.py — Leave / WFH Request Database Model
=====================================================================
Defines the `leave_wfh_request` table — all employee requests in one table.

Non-technical summary:
----------------------
Employees can submit four types of requests, all stored in this single table:

  1. leave        — Request to take a day(s) off.
                    On approval: deducts from leave balance.

  2. wfh          — Request to work from home on specific day(s).
                    On approval: marks attendance session work_mode = "wfh".

  3. missing_time — Request to correct a forgotten checkout.
                    Must be linked to an existing attendance session.
                    On approval: fills in checkout time and marks is_corrected = True.

  4. comp_off     — Request to claim a compensatory day off (worked on a holiday).
                    On approval: credits +1 to comp_off leave balance.

All requests start with status = "pending". Only admins can approve or reject.
Employees can cancel their own pending requests.
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint, Date, ForeignKey,
    Index, String, Time, TIMESTAMP, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LeaveWFHRequest(Base):
    """ORM model for the `leave_wfh_request` table."""
    __tablename__ = "leave_wfh_request"

    __table_args__ = (
        # to_date must be on or after from_date
        CheckConstraint("to_date >= from_date", name="chk_dates"),
        # Fast lookup of all requests by a specific employee
        Index("idx_req_employee", "employee_id"),
        # Fast admin queries filtering by org and status
        Index("idx_req_org_status", "organization_id", "status"),
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

    # Type of request: "leave" | "wfh" | "missing_time" | "comp_off"
    request_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Date range for the request (single day = from_date == to_date)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Employee's explanation for the request
    reason: Mapped[str] = mapped_column(nullable=False)

    # Only used for missing_time requests — points to the session to correct
    linked_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_session.id", ondelete="SET NULL"),
    )

    # Only used for missing_time requests — the exact checkout time the employee missed
    # Stored as TIME (no timezone) and combined with session_date on approval
    checkout_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Lifecycle: "pending" → "approved" or "rejected"
    # Only admins can change status. Employees can delete pending requests.
    status: Mapped[str] = mapped_column(
        String(20), server_default="pending", nullable=False, index=True,
    )

    # Admin who reviewed this request (NULL until reviewed)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee.id", ondelete="SET NULL"),
    )

    # When the admin reviewed it
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # Optional note from admin explaining a rejection
    rejection_note: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
