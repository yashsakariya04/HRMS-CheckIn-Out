import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExtensionCreate(BaseModel):
    task_id: uuid.UUID
    requested_days: int = Field(..., ge=1, le=90)
    reason: str = Field(..., min_length=5, max_length=500)
    comment: Optional[str] = Field(None, max_length=2000)


class ExtensionAction(BaseModel):
    action: str  # "approve" | "reject"
    admin_note: Optional[str] = Field(None, max_length=1000)


class ExtensionResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    requested_by: uuid.UUID
    requested_days: int
    reason: str
    comment: Optional[str]
    status: str
    reviewed_by: Optional[uuid.UUID]
    admin_note: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]

    model_config = {"from_attributes": True}
