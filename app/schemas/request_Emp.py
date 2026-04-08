# app/schemas/request.py
import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, model_validator


VALID_TYPES = {"leave", "wfh", "missing_time", "comp_off"}


class RequestCreate(BaseModel):
    """Body for POST /requests — employee submits a new request."""
    request_type: str
    from_date: date
    to_date: date
    reason: str

    @model_validator(mode="after")
    def validate_dates_and_type(self):
        if self.request_type not in VALID_TYPES:
            raise ValueError(f"request_type must be one of {VALID_TYPES}")
        if self.from_date > self.to_date:
            raise ValueError("from_date must be <= to_date")
        if self.request_type in ("missing_time", "comp_off"):
            if self.from_date != self.to_date:
                raise ValueError(f"{self.request_type} must be a single day (from_date == to_date)")
        return self


class RequestReject(BaseModel):
    """Body for PATCH /requests/{id}/reject."""
    note: Optional[str] = None


class RequestResponse(BaseModel):
    """Full request row returned to the employee."""
    id: uuid.UUID
    request_type: str
    from_date: date
    to_date: date
    reason: str
    status: str
    linked_session_id: Optional[uuid.UUID] = None
    rejection_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestListResponse(BaseModel):
    """Request row returned in admin list — includes employee info."""
    id: uuid.UUID
    request_type: str
    from_date: date
    to_date: date
    reason: str
    status: str
    linked_session_id: Optional[uuid.UUID] = None
    rejection_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    employee_id: uuid.UUID
    employee_name: Optional[str] = None
    employee_email: str

    model_config = {"from_attributes": True}
