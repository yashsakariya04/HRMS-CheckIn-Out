"""
app/models/employee_leave_balance.py — Leave Balance Ledger Model
=================================================================
Defines the `employee_leave_balance` table — monthly leave balance
records for each employee and leave type.

Non-technical summary:
----------------------
Think of this as a monthly bank statement for each employee's leave.
One row = one employee + one leave type + one month.

Balance formula:
    closing_balance = opening_balance + accrued - used + adjusted

Each month:
  - opening_balance : carried over from last month's closing_balance
  - accrued         : leave earned this month (casual = +1/month automatically)
  - used            : leave taken this month (deducted when a leave request is approved)
  - adjusted        : manual admin correction (positive or negative)
  - closing_balance : the final balance at end of month

Leave types tracked:
  - "casual"   : Regular paid leave (1 accrued per month automatically)
  - "comp_off" : Compensatory off (earned by working on holidays, no auto-accrual)

Note: closing_balance CAN be negative (leave debt) — this is intentional.
A negative balance means the employee has taken more leave than they've earned.
Future monthly accruals will offset the debt.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Numeric, String, TIMESTAMP, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class EmployeeLeaveBalance(Base):
    """ORM model for the `employee_leave_balance` table."""
    __tablename__ = "employee_leave_balance"

    __table_args__ = (
        # One row per employee per leave type per month
        UniqueConstraint("employee_id", "leave_type", "year", "month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False,
    )

    # "casual" | "comp_off"
    leave_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Calendar year and month this row covers (e.g. year=2025, month=4 = April 2025)
    year: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)

    # Balance carried forward from the previous month
    opening_balance: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False,
    )

    # Leave earned this month (casual = 1.0, comp_off = 0 unless request approved)
    accrued: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False,
    )

    # Leave consumed this month via approved leave requests
    used: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False,
    )

    # Manual admin adjustment (positive = add leave, negative = deduct)
    adjusted: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False,
    )

    # Computed by service: opening + accrued - used + adjusted
    # Can be negative (leave debt scenario)
    closing_balance: Mapped[float | None] = mapped_column(Numeric(5, 2))

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
