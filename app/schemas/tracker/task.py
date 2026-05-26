from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)


Priority   = Literal["low", "medium", "high", "urgent"]
TaskStatus = Literal[
    "pending_approval", "assigned", "rejected",
    "todo", "in_progress", "in_development", "in_qa", "in_stage", "in_production",
]


# ── Unified task creation (admin + employee) ──────────────────────────────────
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    priority: Priority = "medium"
    deadline: Optional[datetime] = None
    # Empty list = self-assign; one or more UUIDs = assign to others
    assigned_to: list[uuid.UUID] = Field(default_factory=list)
    comment: Optional[str] = Field(None, max_length=2000)

    @field_validator("deadline", mode="after")
    @classmethod
    def normalize_deadline(cls, v: Optional[datetime]) -> Optional[datetime]:
        return _end_of_day(v) if v is not None else None


# ── Add members to an existing task ──────────────────────────────────────────
class TaskAddMembers(BaseModel):
    employee_ids: list[uuid.UUID] = Field(..., min_length=1)


# ── Admin: assign an existing pending bug to employees ────────────────────────
class TaskAssign(BaseModel):
    assigned_to: list[uuid.UUID] = Field(..., min_length=1)
    priority: Priority = "medium"
    deadline: Optional[datetime] = None
    comment: Optional[str] = Field(None, max_length=2000)

    @field_validator("deadline", mode="after")
    @classmethod
    def normalize_deadline(cls, v: Optional[datetime]) -> Optional[datetime]:
        return _end_of_day(v) if v is not None else None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    request_type: str
    priority: str
    status: str
    deadline: Optional[datetime]
    blocked_reason: Optional[str]
    assigned_to: list[uuid.UUID]   # list of member UUIDs
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Inline schemas for full detail response ───────────────────────────────────
class CommentInDetail(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    author_name: Optional[str]
    message: str
    created_at: datetime


class AttachmentInDetail(BaseModel):
    id: uuid.UUID
    file_url: str
    original_filename: str
    file_type: str
    file_size_bytes: Optional[int]
    uploaded_by: uuid.UUID
    created_at: datetime


class ActivityInDetail(BaseModel):
    id: uuid.UUID
    action: str
    detail: Optional[str]
    performed_by: Optional[uuid.UUID]
    performer_name: Optional[str]
    created_at: datetime


class ChecklistItemInDetail(BaseModel):
    id: uuid.UUID
    title: str
    is_done: bool
    created_by: uuid.UUID
    created_at: datetime


class ChecklistInDetail(BaseModel):
    id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime
    items: list[ChecklistItemInDetail] = []


# ── Full detail response (GET /tasks/{id}) ────────────────────────────────────
class TaskFullDetail(TaskResponse):
    assignee_names: list[str] = []
    creator_name: Optional[str] = None
    checklists: list[ChecklistInDetail] = []
    comments: list[CommentInDetail] = []
    attachments: list[AttachmentInDetail] = []
    timeline: list[ActivityInDetail] = []
