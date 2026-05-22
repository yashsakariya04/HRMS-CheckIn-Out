import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SubtaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)


class SubtaskToggle(BaseModel):
    is_done: bool


class SubtaskResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    title: str
    is_done: bool
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
