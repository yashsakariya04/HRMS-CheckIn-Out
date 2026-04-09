"""
app/models/task_entry.py — Task Entry Database Model
=====================================================
Defines the `task_entry` table — individual work items logged
within an attendance session.

Non-technical summary:
----------------------
When an employee checks in (or while checked in), they log what work
they did and how many hours they spent on it. Each task entry records:
  - Which project the work was for
  - A description of what was done
  - How many hours were spent (must be > 0 and <= 24)

Multiple tasks can belong to one attendance session.
Tasks are ordered by `sort_order` for consistent display.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, ForeignKey, Index,
    Numeric, String, TIMESTAMP, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.project import Project


class TaskEntry(Base):
    """ORM model for the `task_entry` table."""
    __tablename__ = "task_entry"

    __table_args__ = (
        # Hours must be a positive number not exceeding 24
        CheckConstraint("hours_logged > 0 AND hours_logged <= 24", name="chk_hours"),
        # Indexes for fast lookups by session, employee, and project
        Index("idx_tasks_session", "session_id"),
        Index("idx_tasks_employee", "employee_id"),
        Index("idx_tasks_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # The attendance session this task belongs to
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_session.id", ondelete="CASCADE"), nullable=False,
    )

    # The project this work was done for (RESTRICT = cannot delete a project
    # that has task entries referencing it)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), nullable=False,
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False,
    )

    # Free-text description of the work done
    description: Mapped[str] = mapped_column(nullable=False)

    # Hours spent on this task (decimal, e.g. 1.5 = 1 hour 30 minutes)
    hours_logged: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    # Display order within the session (0-based, assigned at creation time)
    sort_order: Mapped[int] = mapped_column(server_default="0", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )

    # Eagerly load the related Project so we can access task.project.name
    project: Mapped["Project"] = relationship("Project", lazy="joined")
