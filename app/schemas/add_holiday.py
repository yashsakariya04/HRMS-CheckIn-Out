"""
app/schemas/add_holiday.py — Holiday Management Schemas
=======================================================
Pydantic schemas for admin endpoints that create and manage holidays.

Non-technical summary:
----------------------
Admins add official holidays to the company calendar.
These schemas define what data is required when adding a holiday.

  - HolidayType : Enum of valid holiday categories
  - SetHoliday  : Data required to create a new holiday
"""

from datetime import date
from enum import Enum

from pydantic import BaseModel


class HolidayType(str, Enum):
    """
    Valid categories for a holiday.

    PUBLIC   : Government/national public holiday (e.g. Independence Day)
    INTERNAL : Company-specific off-day (e.g. company anniversary, team offsite)
    OTHER    : Any other type of holiday
    """
    PUBLIC = "public"
    INTERNAL = "internal"
    OTHER = "other"


class SetHoliday(BaseModel):
    """Body for POST /holiday/add — admin adds a new holiday."""
    name: str           # Display name (e.g. "Diwali", "Christmas")
    type: HolidayType   # Category from the HolidayType enum above
    date: date          # The actual date of the holiday (cannot be in the past)
