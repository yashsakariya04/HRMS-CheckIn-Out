import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, ForeignKey, Index, String, Text,
    TIMESTAMP, text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class TrackerDuplicateGroup(Base):
    """
    One auto-detected group of similar tasks assigned to the same developer.
    Created (or refreshed) when the developer opens their dashboard.
    Deleted when:
      - the developer chooses Keep All 
      - a merge request is approved and tasks are merged
    """
    __tablename__ = "tracker_duplicate_group"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    # The developer who owns this group (all tasks in the group are assigned to them)
    developer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False
    )
    # Human-readable label auto-generated from the first task title
    label: Mapped[str | None] = mapped_column(String(500))
    # "open" → awaiting developer action
    # "kept" → developer chose Keep All
    # "merge_requested" → merge request submitted
    # "merged" → approved and merged
    # "rejected" → merge request rejected
    status: Mapped[str] = mapped_column(
        String(20), server_default="open", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','kept','merge_requested','merged','rejected')",
            name="chk_dup_group_status",
        ),
        Index("idx_dup_group_developer", "developer_id"),
        Index("idx_dup_group_status", "status"),
    )

    members: Mapped[list["TrackerDuplicateGroupMember"]] = relationship(
        "TrackerDuplicateGroupMember", cascade="all, delete-orphan", lazy="selectin"
    )


class TrackerDuplicateGroupMember(Base):
    """Each task that belongs to a duplicate group."""
    __tablename__ = "tracker_duplicate_group_member"

    __table_args__ = (
        UniqueConstraint("group_id", "task_id", name="uq_dup_group_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracker_duplicate_group.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracker_task.id", ondelete="CASCADE"), nullable=False
    )
    # Similarity score to the first task in the group (0.0–1.0)
    similarity_score: Mapped[float | None] = mapped_column()
    # After merge: "primary" task remains, "merged" tasks are closed
    role: Mapped[str] = mapped_column(
        String(10), server_default="candidate", nullable=False
    )  # candidate | primary | merged


class TrackerMergeRequest(Base):
    """
    Developer's request to merge a duplicate group into one primary task.
    Managers of all involved tasks must review it.
    """
    __tablename__ = "tracker_merge_request"

    __table_args__ = (
        Index("idx_merge_req_group", "group_id"),
        Index("idx_merge_req_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracker_duplicate_group.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), nullable=False
    )
    # The task the developer wants to keep and work on
    primary_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracker_task.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default="pending", nullable=False
    )  # pending | approved | rejected
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee.id", ondelete="SET NULL")
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
