# app/models/audit_log.py
"""
Audit log — append-only. Never update or delete rows.
Records every sensitive admin action (approve, reject, modify).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, BigInteger, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_time", "created_at"),
    )

    # BigSerial integer — not UUID — for efficient sequential reads
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee.id", ondelete="SET NULL")
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)

    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    old_data: Mapped[dict | None] = mapped_column(JSONB)

    new_data: Mapped[dict | None] = mapped_column(JSONB)

    ip_address: Mapped[str | None] = mapped_column(INET)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )