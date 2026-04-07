# app/schemas/attendance.py
"""
Pydantic schemas for attendance and task endpoints.

CheckInRequest  — what frontend sends when checking in
SessionResponse — what we return after check-in / for today's session
"""

import uuid
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


# ─── Task schemas ──────────────────────────────────────────────────────────

class TaskInput(BaseModel):
    """One task entry submitted during check-in."""
    project_id: uuid.UUID
    description: str
    hours: float


class TaskResponse(BaseModel):
    """One task entry returned in API responses."""
    id: uuid.UUID
    project_id: uuid.UUID
    description: str
    hours: float = Field(validation_alias="hours_logged")

    model_config = {"from_attributes": True}


# ─── Check-in ──────────────────────────────────────────────────────────────

class CheckInRequest(BaseModel):
    """
    Body for POST /attendance/check-in.
    Frontend sends all tasks together with the check-in.
    At least one task is required.
    """
    tasks: List[TaskInput]


# ─── Session response ──────────────────────────────────────────────────────

class SessionResponse(BaseModel):
    """
    Returned after check-in, check-out, or GET /attendance/today.

    check_out_at = None means session is still open.
    total_hours  = None until checkout.
    """
    id: uuid.UUID
    session_date: date
    check_in_at: datetime
    check_out_at: Optional[datetime] = None
    total_hours: Optional[float] = None
    work_mode: str
    is_corrected: bool
    tasks: List[TaskResponse] = []

    model_config = {"from_attributes": True}


# ─── Project schema ────────────────────────────────────────────────────────

class ProjectResponse(BaseModel):
    """Returned by GET /projects — drives the project dropdown."""
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


# ─── Holiday schema ────────────────────────────────────────────────────────

class HolidayResponse(BaseModel):
    """Returned by GET /holidays — populates the holiday list modal."""
    id: uuid.UUID
    name: str
    holiday_date: date
    holiday_type: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Balance schema ────────────────────────────────────────────────────────

class BalanceResponse(BaseModel):
    """
    One leave balance row.
    Returned as a list by GET /balances/me.
    Frontend reads:
        leave_type == 'casual'   → Leaves left
        leave_type == 'comp_off' → Comp off
    """
    leave_type: str
    year: int
    month: int
    opening_balance: float
    accrued: float
    used: float
    adjusted: float
    closing_balance: float

    model_config = {"from_attributes": True}

# ─── Daily tasks page schemas ──────────────────────────────────────────────

class TaskInSession(BaseModel):
    """One task inside a session row on the Daily tasks page."""
    id: uuid.UUID
    description: str
    hours_logged: float
    project_id: uuid.UUID
    project_name: str

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """One row in the Daily tasks table."""
    id: uuid.UUID
    session_date: date
    check_in_at: datetime
    check_out_at: Optional[datetime] = None
    total_hours: Optional[float] = None
    work_mode: str
    is_corrected: bool
    tasks: List[TaskInSession] = []
    tasks_summary: str = ""

    model_config = {"from_attributes": True}
