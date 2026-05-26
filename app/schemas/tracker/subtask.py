import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Checklist ─────────────────────────────────────────────────────────────────

class ChecklistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ChecklistRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class SubtaskItemResponse(BaseModel):
    id: uuid.UUID
    checklist_id: uuid.UUID
    title: str
    is_done: bool
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ChecklistResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime
    items: list[SubtaskItemResponse] = []

    model_config = {"from_attributes": True}


# ── Subtask items ─────────────────────────────────────────────────────────────

class SubtaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)


class SubtaskToggle(BaseModel):
    is_done: bool


# Keep old SubtaskResponse as alias for backward compat in task full detail
SubtaskResponse = SubtaskItemResponse
