from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

#  Input for creating project
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


#  Output when returning project
class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True