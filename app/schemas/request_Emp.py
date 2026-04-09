"""
app/schemas/request_Emp.py — Leave/WFH Request Pydantic Schemas
================================================================
Defines the data shapes for employee request endpoints (leave, WFH,
missing time, comp-off).

Non-technical summary:
----------------------
These schemas define what data the frontend sends when submitting a
request, and what the backend returns when listing requests.

  - RequestCreate      : Employee submits a new request
  - RequestReject      : Admin rejects a request (optional note)
  - RequestResponse    : Full request details returned to the employee
  - RequestListResponse: Request details returned in admin list (includes employee info)
  - LeaveSummaryRow    : Per-employee leave summary for admin dashboard
"""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, model_validator

# All valid request types — validated in RequestCreate
VALID_TYPES = {"leave", "wfh", "missing_time", "comp_off"}


class RequestCreate(BaseModel):
    """
    Body for POST /requests — employee submits a new request.

    Validation rules (enforced automatically):
      - request_type must be one of: leave, wfh, missing_time, comp_off
      - from_date must be on or before to_date
      - missing_time and comp_off must be a single day (from_date == to_date)
    """
    request_type: str
    from_date: date
    to_date: date
    reason: str

    @model_validator(mode="after")
    def validate_dates_and_type(self):
        """Cross-field validation: type, date order, and single-day constraint."""
        if self.request_type not in VALID_TYPES:
            raise ValueError(f"request_type must be one of {VALID_TYPES}")
        if self.from_date > self.to_date:
            raise ValueError("from_date must be <= to_date")
        if self.request_type in ("missing_time", "comp_off"):
            if self.from_date != self.to_date:
                raise ValueError(
                    f"{self.request_type} must be a single day (from_date == to_date)"
                )
        return self


class RequestReject(BaseModel):
    """Body for PATCH /requests/{id}/reject — admin provides optional rejection note."""
    note: Optional[str] = None


class RequestResponse(BaseModel):
    """Full request row returned to the employee who owns the request."""
    id: uuid.UUID
    request_type: str
    from_date: date
    to_date: date
    reason: str
    status: str                              # "pending" | "approved" | "rejected"
    linked_session_id: Optional[uuid.UUID] = None  # Only set for missing_time requests
    rejection_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestListResponse(BaseModel):
    """
    Request row returned in the admin list view.
    Includes employee details so the admin knows who submitted the request.
    """
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


class LeaveSummaryRow(BaseModel):
    """Per-employee leave summary row for the admin dashboard."""
    employee_name: str
    this_month_leaves: int
    previous_months: dict[str, int]  # e.g. {"Feb 2025": 1, "Jan 2025": 2}
    leaves_balance: int
