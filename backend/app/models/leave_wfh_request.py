import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, Boolean, Date,
    Numeric, CheckConstraint, UniqueConstraint, Index, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

class LeaveRequest(Base):
    __tablename__ = "leave_wfh_request"

    __table_args__ = (
        CheckConstraint("to_date >= from_date"),
        Index("idx_req_employee", "employee_id"),
        Index("idx_req_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False
    )

    request_type: Mapped[str] = mapped_column(String(20), nullable=False)

    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)

    reason: Mapped[str] = mapped_column(nullable=False)

    linked_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_session.id", ondelete="SET NULL")
    )

    status: Mapped[str] = mapped_column(
        String(20), server_default="pending", nullable=False
    )

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee.id", ondelete="SET NULL")
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    rejection_note: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
    TIMESTAMP(timezone=True),
    server_default=text("now()"),
    onupdate=text("now()"),
    nullable=False

    )