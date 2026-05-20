from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


Priority    = Literal["low", "medium", "high", "urgent"]
TaskStatus  = Literal[
    "pending_approval", "assigned", "todo", "in_progress",
    "blocked", "testing", "completed", "rejected",
]


# ── Employee: create a bug report (title + description + files only) ──────────
class BugReportCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None


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
    blocked_reason: Optional[str] = Field(None, max_length=500)


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


class TaskDetail(TaskResponse):
    assignee_name: Optional[str] = None
    creator_name: Optional[str] = None
