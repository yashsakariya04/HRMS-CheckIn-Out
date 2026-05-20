import uuid
from datetime import datetime

from pydantic import BaseModel


class ActivityLogResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    action: str
    detail: str | None
    performed_by: uuid.UUID | None
    performer_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
