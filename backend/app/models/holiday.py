import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, Boolean, Date,
    Numeric, CheckConstraint, UniqueConstraint, Index, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base

class Holiday(Base):
    __tablename__ = "holiday"

    __table_args__ = (
        UniqueConstraint("organization_id", "holiday_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False
    )

    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    holiday_type: Mapped[str] = mapped_column(
        String(30), server_default="national", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )