import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    file_url: str
    original_filename: str
    file_type: str
    file_size_bytes: Optional[int]
    uploaded_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
