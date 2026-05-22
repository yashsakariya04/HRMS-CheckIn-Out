from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


Priority   = Literal["low", "medium", "high", "urgent"]
TaskStatus = Literal[
    "pending_approval", "assigned", "rejected",
    "todo", "in_progress", "in_development", "in_qa", "in_stage", "in_production",
]


# ── Employee: submit a bug report ─────────────────────────────────────────────
class BugReportCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None


# ── Employee: self-assign a task (no admin approval needed) ───────────────────
class EmployeeTaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    priority: Priority = "medium"
    deadline: datetime


# ── Admin: create & directly assign a custom task ────────────────────────────
class AdminTaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    assigned_to: uuid.UUID
    priority: Priority = "medium"
    deadline: datetime
    comment: Optional[str] = Field(None, max_length=2000)


# ── Admin: assign an existing pending bug to an employee ─────────────────────
class TaskAssign(BaseModel):
    assigned_to: uuid.UUID
    priority: Priority = "medium"
    deadline: Optional[datetime] = None
    comment: Optional[str] = Field(None, max_length=2000)


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
    assigned_to: Optional[uuid.UUID]
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


class SubtaskInDetail(BaseModel):
    id: uuid.UUID
    title: str
    is_done: bool
    created_by: uuid.UUID
    created_at: datetime


# ── Full detail response (GET /tasks/{id}) ────────────────────────────────────
class TaskFullDetail(TaskResponse):
    assignee_name: Optional[str] = None
    creator_name: Optional[str] = None
    subtasks: list[SubtaskInDetail] = []
    comments: list[CommentInDetail] = []
    attachments: list[AttachmentInDetail] = []
    timeline: list[ActivityInDetail] = []
