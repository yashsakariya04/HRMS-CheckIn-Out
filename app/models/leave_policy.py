"""
app/models/leave_policy.py — Leave Policy Database Model
=========================================================
Defines the `leave_policy` table — rules for how leave is accrued
and carried forward for each leave type per organization.

Non-technical summary:
----------------------
This table stores the rules that govern leave for the company:
  - How many leave days does an employee earn per month?
  - How many unused days can be carried forward to the next month?

One row per leave type per organization.
The monthly rollover job (leave_rollover.py) reads these rules
when creating new monthly balance records.

Example row:
  leave_type    = "casual"
  days_per_month = 1.0   → employees earn 1 casual leave per month
  max_carry_fwd  = 1.0   → at most 1 unused day carries to next month
  is_active      = True
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LeavePolicy(Base):
    """ORM model for the `leave_policy` table."""
    __tablename__ = "leave_policy"

    __table_args__ = (
        # One policy per leave type per organization
        UniqueConstraint("organization_id", "leave_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False,
    )

    # "casual" | "sick" | "earned" | "comp_off"
    leave_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # How many leave days are credited to employees each month
    days_per_month: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="1", nullable=False,
    )

    # Maximum unused days that roll over to the next month
    max_carry_fwd: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="1", nullable=False,
    )

    # Inactive policies are ignored by the rollover job
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False,
    )
