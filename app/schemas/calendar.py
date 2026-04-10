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
          {
            "employee_id": "efe2ea44-a159-447c-a89c-d3bbcd6b2fcf",
            "employee_name": "Alice",
            "employee_email": "alice@example.com",
            "type": "leave",
            "from_date": "2025-04-10",
            "to_date": "2025-04-10",
            "reason": "personal work"
          }
        ]
      }
    }

Schemas:
  - CalendarDayEntry : One employee's full leave/WFH entry on a specific date
  - CalendarResponse : Full month calendar with all entries grouped by date
"""

import uuid
from datetime import date
from typing import Dict, List

from pydantic import BaseModel


class CalendarDayEntry(BaseModel):
    """One employee's full leave or WFH entry on a specific calendar date."""
    employee_id: uuid.UUID
    employee_name: str
    employee_email: str
    type: str        # "leave" or "wfh"
    from_date: date  # Original request start date
    to_date: date    # Original request end date
    reason: str


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
