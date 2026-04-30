import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AIAuditLog(Base):
    __tablename__ = "ai_audit_log"

    __table_args__ = (
        Index("idx_ai_audit_employee", "employee_id"),
        Index("idx_ai_audit_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False,
    )
    # ACTION | SQL | DOCS | MULTI_STEP | CHAT | AMBIGUOUS
    intent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action_taken: Mapped[str | None] = mapped_column(String(100))
    api_called: Mapped[str | None] = mapped_column(String(100))
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[str | None] = mapped_column(String(20))   # success | failed | error
    error_message: Mapped[str | None] = mapped_column(Text)
    llm_confidence: Mapped[float | None] = mapped_column(Float)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
