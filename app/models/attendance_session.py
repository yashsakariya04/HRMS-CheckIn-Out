# app/models/attendance_session.py
import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, Boolean, Date,
    Numeric, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List

from app.models import Base

class AttendanceSession(Base):
    __tablename__ = "attendance_session"

    __table_args__ = (
        UniqueConstraint("employee_id", "session_date", name="uq_session_per_day"),
        CheckConstraint(
            "check_out_at IS NULL OR check_out_at > check_in_at",
            name="chk_checkout_after_checkin"
        ),
        Index("idx_sess_emp_date", "employee_id", "session_date"),
        Index("idx_sess_org_date", "organization_id", "session_date"),
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

    session_date: Mapped[date] = mapped_column(Date, nullable=False)

    check_in_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    # NULL = session still open (employee has not checked out)
    check_out_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    # Computed and stored by the service on checkout
    # (decimal hours, e.g. 8.5 = 8h 30m)
    total_hours: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # 'office' | 'wfh' | 'client_site'
    work_mode: Mapped[str] = mapped_column(
        String(20), server_default="office", nullable=False
    )

    # True when a missing_time request was approved and checkout was corrected
    is_corrected: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )

    correction_note: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False
    )

    tasks: Mapped[List["TaskEntry"]] = relationship(
        "TaskEntry", back_populates="session", lazy="joined"
    )