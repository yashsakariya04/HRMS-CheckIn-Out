import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, Boolean, Date,
    Numeric, CheckConstraint, UniqueConstraint, Index, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base

class LeaveBalance(Base):
    __tablename__ = "employee_leave_balance"

    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type", "year", "month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False
    )

    leave_type: Mapped[str] = mapped_column(String(30), nullable=False)

    year: Mapped[int] = mapped_column(nullable=False)

    month: Mapped[int] = mapped_column(nullable=False)

    opening_balance: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False
    )

    accrued: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False
    )

    used: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False
    )

    adjusted: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False
    )

    closing_balance: Mapped[float | None] = mapped_column(
        Numeric(5, 2)
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )