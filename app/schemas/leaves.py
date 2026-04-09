"""
app/schemas/leaves.py — Employee Leave History Schemas
======================================================
Pydantic schemas for the GET /leaves/me endpoint — returns an
employee's approved leave history grouped by month.

Non-technical summary:
----------------------
When an employee opens their leave history page, the backend returns:
  1. This month's leave dates (individual dates they were on leave)
  2. Previous months' leave summaries (how many days each past month)

Schemas:
  - CurrentMonthLeaves  : Leave dates for the current calendar month
  - PreviousMonthLeaves : Leave summary for a past month
  - LeavesResponse      : The full response combining both of the above
"""

from typing import List

from pydantic import BaseModel


class CurrentMonthLeaves(BaseModel):
    """Leave dates taken in the current calendar month."""
    month: int          # Month number (1-12)
    year: int
    dates: List[str]    # ISO date strings, e.g. ["2025-04-10", "2025-04-11"]


class PreviousMonthLeaves(BaseModel):
    """Leave summary for a past month."""
    month: int
    year: int
    total_days: int     # Total leave days taken that month
    dates: List[str]    # Individual dates (ISO format)


class LeavesResponse(BaseModel):
    """Full response for GET /leaves/me."""
    current_month: CurrentMonthLeaves
    previous_months: List[PreviousMonthLeaves]  # Sorted newest first
