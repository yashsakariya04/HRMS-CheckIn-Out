import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)


class CommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    author_name: Optional[str] = None
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
