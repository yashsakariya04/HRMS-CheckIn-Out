import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, TIMESTAMP, text, Boolean, Date,
    Numeric, CheckConstraint, UniqueConstraint, Index, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

class TaskEntry(Base):
    __tablename__ = "task_entry"

    __table_args__ = (
        CheckConstraint("hours_logged > 0 AND hours_logged <= 24"),
        Index("idx_tasks_session", "session_id"),
        Index("idx_tasks_employee", "employee_id"),
        Index("idx_tasks_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_session.id", ondelete="CASCADE"),
        nullable=False
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False
    )

    description: Mapped[str] = mapped_column(nullable=False)

    hours_logged: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False
    )

    sort_order: Mapped[int] = mapped_column(
        server_default="0", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
    TIMESTAMP(timezone=True),
    server_default=text("now()"),
    onupdate=text("now()"),
    nullable=False

    )