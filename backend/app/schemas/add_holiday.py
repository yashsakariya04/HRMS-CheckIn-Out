from enum import Enum

class HolidayType(str, Enum):
    PUBLIC= "public"
    INTERNAL= "internal"
    OTHER= "other"


from pydantic import BaseModel 
from datetime import date
class SetHoliday(BaseModel):
    name: str
    type: HolidayType
    date: date 