# app/models/employee_leave_balance.py
import uuid
from datetime import datetime

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text,
    Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base


class EmployeeLeaveBalance(Base):
    """
    Monthly leave ledger. One row per employee per leave_type per month.

    Formula:
        closing_balance = opening_balance + accrued - used + adjusted
    Next month:
        opening_balance = MIN(prev_closing, max_carry_fwd from leave_policy)
    """
    __tablename__ = "employee_leave_balance"

    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type", "year", "month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False
    )

    # 'casual' | 'sick' | 'earned' | 'comp_off'
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

    # Computed by service: opening + accrued - used + adjusted
    closing_balance: Mapped[float | None] = mapped_column(Numeric(5, 2))

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )