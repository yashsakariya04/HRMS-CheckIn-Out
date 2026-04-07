# schemas/leave_request.py

from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import date, datetime


class LeaveRequestOut(BaseModel):
    id: uuid.UUID
    employee_name: str
    request_type: str       # "leave" | "wfh"
    from_date: date
    to_date: date
    reason: str
    status: str             # "pending" | "approved" | "rejected"

    model_config = {"from_attributes": True}


class ReviewRequestBody(BaseModel):
    rejection_note: Optional[str] = None   # only needed when rejecting


class LeaveSummaryRow(BaseModel):
    employee_name: str
    this_month_leaves: int
    previous_months: dict[str, int]        # e.g. {"Feb": 1, "Jan": 1}
    leaves_balance: int