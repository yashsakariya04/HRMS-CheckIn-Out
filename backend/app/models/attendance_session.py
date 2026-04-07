import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, Boolean, Date,
    Numeric, CheckConstraint, UniqueConstraint, Index, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base


class AttendanceSession(Base):
    __tablename__ = "attendance_session"

    __table_args__ = (
        UniqueConstraint("employee_id", "session_date"),
        CheckConstraint("check_out_at IS NULL OR check_out_at > check_in_at"),
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

    check_out_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    total_hours: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )

    work_mode: Mapped[str] = mapped_column(
        String(20),
        server_default="office",
        nullable=False
    )

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
    onupdate=text("now()"),
    nullable=False

    )
    
    