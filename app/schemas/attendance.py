"""
app/schemas/attendance.py — Attendance & Task Pydantic Schemas
==============================================================
Defines the data shapes for attendance check-in/check-out endpoints,
task logging, leave balances, and the daily sessions list.

Non-technical summary:
----------------------
These are the "data contracts" between the frontend and backend.
When the frontend sends data or the backend returns data, it must
match one of these shapes exactly — Pydantic enforces this automatically.

Schemas:
  - TaskInput         : One task submitted during check-in
  - TaskResponse      : One task returned in API responses
  - CheckInRequest    : Full check-in body (must include at least one task)
  - SessionResponse   : Returned after check-in, check-out, or GET /today
  - ProjectResponse   : Project item for dropdown lists
  - HolidayResponse   : Holiday item for the holiday list
  - BalanceResponse   : One leave balance row (casual or comp_off)
  - TaskInSession     : Task row shown in the daily sessions table
  - SessionListResponse: One row in the daily sessions history table
"""

import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TaskInput(BaseModel):
    """One task entry submitted by the employee during check-in."""
    project_id: uuid.UUID   # Which project this work belongs to
    description: str        # What was done (free text)
    hours: float            # Time spent (e.g. 2.5 = 2 hours 30 minutes)


class TaskResponse(BaseModel):
    """One task entry returned in API responses."""
    id: uuid.UUID
    project_id: uuid.UUID
    description: str
    # `hours_logged` in the DB is aliased to `hours` in the API response
    hours: float = Field(validation_alias="hours_logged")

    model_config = {"from_attributes": True}


class CheckInRequest(BaseModel):
    """
    Body for POST /attendance/check-in.

    The employee must provide at least one task when checking in.
    All tasks for the day are submitted together at check-in time.
    """
    tasks: List[TaskInput]  # At least one task required (enforced in service layer)


class SessionResponse(BaseModel):
    """
    Returned after check-in, check-out, or GET /attendance/today.

    check_out_at = None  → employee is still checked in (session open)
    total_hours  = None  → not yet calculated (only set on checkout)
    """
    id: uuid.UUID
    session_date: date
    check_in_at: datetime
    check_out_at: Optional[datetime] = None
    total_hours: Optional[float] = None
    work_mode: str       # "office" | "wfh" | "client_site"
    is_corrected: bool   # True if checkout was corrected by admin
    tasks: List[TaskResponse] = []

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    """Returned by GET /project/ — drives the project dropdown in the UI."""
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class HolidayResponse(BaseModel):
    """Returned by GET /holiday/ — populates the holiday list."""
    id: uuid.UUID
    name: str
    holiday_date: date
    holiday_type: Optional[str] = None

    model_config = {"from_attributes": True}


class BalanceResponse(BaseModel):
    """
    One leave balance row for a specific month.
    Returned as a list by GET /balances/me.

    Frontend uses:
      leave_type == "casual"   → "Leaves left" display
      leave_type == "comp_off" → "Comp off" display
    """
    leave_type: str
    year: int
    month: int
    opening_balance: float
    accrued: float
    used: float
    adjusted: float
    closing_balance: Optional[float] = None  # The spendable balance

    model_config = {"from_attributes": True}


class TaskInSession(BaseModel):
    """One task row shown inside a session on the Daily Tasks page."""
    id: uuid.UUID
    description: str
    hours_logged: float
    project_id: uuid.UUID
    project_name: str   # Joined from the project table for display

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """One row in the attendance history / daily tasks table."""
    id: uuid.UUID
    session_date: date
    check_in_at: datetime
    check_out_at: Optional[datetime] = None
    total_hours: Optional[float] = None
    work_mode: str
    is_corrected: bool
    tasks: List[TaskInSession] = []
    tasks_summary: str = ""  # Comma-joined task descriptions for quick display

    model_config = {"from_attributes": True}
