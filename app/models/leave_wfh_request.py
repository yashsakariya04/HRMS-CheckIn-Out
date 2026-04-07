# app/models/leave_wfh_request.py
import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, Date,
    CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LeaveWFHRequest(Base):
    """
    All 4 request types in one table.

    Approval side-effects (handled by leave_service):
        leave        → balance.used += (to_date - from_date).days + 1
        wfh          → session.work_mode = 'wfh'
        missing_time → session.check_out_at filled, is_corrected = True
        comp_off     → balance.accrued += 1
    """
    __tablename__ = "leave_wfh_request"

    __table_args__ = (
        CheckConstraint("to_date >= from_date", name="chk_dates"),
        Index("idx_req_employee", "employee_id"),
        Index("idx_req_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )

    # 'leave' | 'wfh' | 'missing_time' | 'comp_off'
    request_type: Mapped[str] = mapped_column(String(20), nullable=False)

    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)

    reason: Mapped[str] = mapped_column(nullable=False)

    # Only used for missing_time — points to the session that needs correction
    linked_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_session.id", ondelete="SET NULL")
    )

    # RULE: All requests start 'pending'. Only admin can change to approved/rejected.
    status: Mapped[str] = mapped_column(
        String(20), server_default="pending", nullable=False, index=True
    )

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee.id", ondelete="SET NULL")
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    rejection_note: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False
    )