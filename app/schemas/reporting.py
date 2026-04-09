"""
app/schemas/reporting.py — Admin Reporting Pydantic Schemas
============================================================
Defines the data shapes for the admin reporting endpoints.

Non-technical summary:
----------------------
Admins can view detailed attendance reports for any employee.
These schemas define what the reporting API returns.

  - EmployeeDropdownItem : One employee in the "select employee" dropdown
  - AttendanceRow        : One day's attendance record in the report table
  - ReportingResponse    : Full report for one employee (avg hours + all records)
"""

from datetime import date, datetime

from pydantic import BaseModel


class EmployeeDropdownItem(BaseModel):
    """
    One employee entry for the admin's employee selector dropdown.
    Used by GET /reporting/employees.
    """
    id: str                      # Employee UUID as string
    full_name: str               # Display name
    designation: str | None      # Job title (may be empty)

    model_config = {"from_attributes": True}


class AttendanceRow(BaseModel):
    """
    One day's attendance record shown in the admin report table.

    `tasks` is a comma-joined string of all task descriptions for that day
    (e.g. "Fixed login bug, Code review, Team meeting").
    """
    date: date
    tasks: str                       # Comma-joined task descriptions
    check_in_at: datetime
    check_out_at: datetime | None    # None if the employee never checked out


class ReportingResponse(BaseModel):
    """
    Full attendance report for one employee.
    Returned by GET /reporting/{employee_id}.

    avg_hours_this_month : Average daily hours worked this calendar month
    records              : List of attendance rows (newest first)
    """
    avg_hours_this_month: float
    records: list[AttendanceRow]
