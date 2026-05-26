import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, ForeignKey, Index, String, Text, TIMESTAMP, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class TrackerTaskMember(Base):
    """Association table — one row per (task, employee) pair."""
    __tablename__ = "tracker_task_member"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracker_task.id", ondelete="CASCADE"), primary_key=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )


class TrackerTask(Base):
    __tablename__ = "tracker_task"

    __table_args__ = (
        CheckConstraint(
            "request_type IN ('bug', 'task')",
            name="chk_tracker_task_request_type",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="chk_tracker_task_priority",
        ),
        CheckConstraint(
            "status IN ('pending_approval','assigned','todo','in_progress',"
            "'in_development','in_qa','in_stage','in_production','rejected')",
            name="chk_tracker_task_status",
        ),
        Index("idx_tracker_task_created_by", "created_by"),
        Index("idx_tracker_task_status", "status"),
        Index("idx_tracker_task_deadline", "deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    request_type: Mapped[str] = mapped_column(String(10), nullable=False)  # bug | task
    priority: Mapped[str] = mapped_column(String(10), server_default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="pending_approval", nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    blocked_reason: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    members: Mapped[list["TrackerTaskMember"]] = relationship(
        "TrackerTaskMember", cascade="all, delete-orphan", lazy="selectin"
    )
