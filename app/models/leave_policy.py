# app/models/leave_policy.py
import uuid

from sqlalchemy import (
    String, ForeignKey, text, Boolean,
    Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LeavePolicy(Base):
    __tablename__ = "leave_policy"

    __table_args__ = (
        UniqueConstraint("organization_id", "leave_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )

    # 'casual' | 'sick' | 'earned' | 'comp_off'
    leave_type: Mapped[str] = mapped_column(String(30), nullable=False)

    days_per_month: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="1", nullable=False
    )

    max_carry_fwd: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="1", nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )