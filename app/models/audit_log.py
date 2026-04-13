"""
app/models/audit_log.py — Audit Log Database Model
===================================================
Defines the `audit_log` table — an append-only record of every
sensitive admin action in the system.

Non-technical summary:
----------------------
Every time an admin does something important (approves a leave,
rejects a request, modifies data), a record is written here.
This log is NEVER updated or deleted — it's a permanent trail
of who did what and when.

This is useful for:
  - Accountability: knowing which admin approved/rejected a request
  - Debugging: tracing what changed and when
  - Compliance: audit trails required by some organizations

Uses a BigInteger (auto-incrementing integer) as the primary key
instead of UUID — this makes sequential reads much faster since
rows are physically ordered by insertion time.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, JSON, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import types


class _INET(types.TypeDecorator):
    """Cross-dialect INET: uses native INET on PostgreSQL, String(45) elsewhere."""
    impl = types.String(45)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import INET as PG_INET
            return dialect.type_descriptor(PG_INET())
        return dialect.type_descriptor(types.String(45))

from app.models import Base


class AuditLog(Base):
    """
    ORM model for the `audit_log` table.

    IMPORTANT: Never UPDATE or DELETE rows in this table.
    It is an append-only immutable log.
    """
    __tablename__ = "audit_log"

    __table_args__ = (
        # Fast lookup of all log entries for a specific record (e.g. a request)
        Index("idx_audit_entity", "entity_type", "entity_id"),
        # Fast lookup of recent activity by time
        Index("idx_audit_time", "created_at"),
    )

    # Sequential integer — faster for ordered reads than UUID
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # The admin (or system) who performed the action. NULL if the actor was deleted.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee.id", ondelete="SET NULL"),
    )

    # What was done (e.g. "approve_leave", "reject_request", "add_employee")
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # What type of record was affected (e.g. "leave_wfh_request", "employee")
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # The UUID of the specific record that was affected
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Snapshot of the record BEFORE the change (JSON)
    old_data: Mapped[dict | None] = mapped_column(JSON)

    # Snapshot of the record AFTER the change (JSON)
    new_data: Mapped[dict | None] = mapped_column(JSON)

    # IP address of the client that made the request (for security tracking)
    ip_address: Mapped[str | None] = mapped_column(_INET)

    # When this log entry was created (immutable)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
