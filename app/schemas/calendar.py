# app/schemas/calendar.py
from typing import Dict, List
from pydantic import BaseModel


class CalendarDayEntry(BaseModel):
    """One employee entry on a calendar date."""
    employee_name: str
    type: str  # 'leave' | 'wfh'


class CalendarResponse(BaseModel):
    """Full calendar response for a given month/year."""
    month: int
    year: int
    data: Dict[str, List[CalendarDayEntry]]
