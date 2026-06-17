import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.tracker.task import _end_of_day


class ExtensionCreate(BaseModel):
    task_id: uuid.UUID
    new_deadline: datetime
    reason: str = Field(..., min_length=5, max_length=500)
    comment: Optional[str] = Field(None, max_length=2000)

    @field_validator("new_deadline", mode="after")
    @classmethod
    def normalize_new_deadline(cls, v: datetime) -> datetime:
        return _end_of_day(v)


class ExtensionAction(BaseModel):
    action: str  # "approve" | "reject"
    admin_note: Optional[str] = Field(None, max_length=1000)


class ExtensionResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    requested_by: uuid.UUID
    new_deadline: datetime
    reason: str
    comment: Optional[str]
    status: str
    reviewed_by: Optional[uuid.UUID]
    admin_note: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]

    model_config = {"from_attributes": True}
