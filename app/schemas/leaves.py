# app/schemas/leaves.py
from typing import List
from pydantic import BaseModel


class CurrentMonthLeaves(BaseModel):
    """Leave dates for the current month."""
    month: int
    year: int
    dates: List[str]  # ISO date strings e.g. "2026-04-10"


class PreviousMonthLeaves(BaseModel):
    """Leave summary for a past month."""
    month: int
    year: int
    total_days: int
    dates: List[str]


class LeavesResponse(BaseModel):
    """Full response for GET /leaves/me."""
    current_month: CurrentMonthLeaves
    previous_months: List[PreviousMonthLeaves]
