from pydantic import BaseModel
from datetime import date, datetime


class EmployeeDropdownItem(BaseModel):
    id: str
    full_name: str
    designation: str | None

    model_config = {"from_attributes": True}


class AttendanceRow(BaseModel):
    date: date
    tasks: str
    check_in_at: datetime
    check_out_at: datetime | None


class ReportingResponse(BaseModel):
    avg_hours_this_month: float
    records: list[AttendanceRow]
