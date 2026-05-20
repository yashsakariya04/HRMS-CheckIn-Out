import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class TrackerActivityLog(Base):
    """Append-only timeline entry per task. Never update or delete rows."""
    __tablename__ = "tracker_activity_log"

    __table_args__ = (
        Index("idx_tracker_activity_task_id", "task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracker_task.id", ondelete="CASCADE"), nullable=False
    )
    # Human-readable action label, e.g. "status_changed", "comment_added"
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    # Full sentence shown in the timeline, e.g. "Status changed to In Progress"
    detail: Mapped[str | None] = mapped_column(Text)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
