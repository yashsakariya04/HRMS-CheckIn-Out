"""
app/schemas/calendar.py — Calendar Pydantic Schemas
====================================================
Defines the data shape for the monthly leave/WFH calendar endpoint.

Non-technical summary:
----------------------
The calendar page shows which employees are on leave or WFH on each
day of the selected month. This schema defines what the backend returns.

Example response:
    {
      "month": 4,
      "year": 2025,
      "data": {
        "2025-04-10": [
          {"employee_name": "Alice", "type": "leave"},
          {"employee_name": "Bob",   "type": "wfh"}
        ],
        "2025-04-15": [
          {"employee_name": "Charlie", "type": "leave"}
        ]
      }
    }

Schemas:
  - CalendarDayEntry : One employee's status on a specific date
  - CalendarResponse : Full month calendar with all entries grouped by date
"""

from typing import Dict, List

from pydantic import BaseModel


class CalendarDayEntry(BaseModel):
    """One employee's leave or WFH entry on a specific calendar date."""
    employee_name: str
    type: str  # "leave" or "wfh"


class CalendarResponse(BaseModel):
    """
    Full calendar response for a given month and year.

    `data` is a dictionary where:
      - key   : ISO date string (e.g. "2025-04-10")
      - value : List of employees on leave/WFH that day
    """
    month: int
    year: int
    data: Dict[str, List[CalendarDayEntry]]
