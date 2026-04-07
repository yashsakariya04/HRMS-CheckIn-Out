import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, Boolean, Date,
    Numeric, CheckConstraint, UniqueConstraint, Index, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base

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
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False
    )

    leave_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    days_per_month: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="1", nullable=False
    )

    max_carry_fwd: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default="1", nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )