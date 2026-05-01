"""
app/schemas/add_user.py — Employee Management Schemas
=====================================================
Pydantic schemas for admin endpoints that create and update employees.

Non-technical summary:
----------------------
Admins use these schemas when:
  - Adding a new employee to the system (before they log in for the first time)
  - Updating an employee's profile (name or photo)

  - CreateEmployeeRequest : Data needed to register a new employee
  - UpdateProfileRequest  : Data an employee can update on their own profile
  - EmployeeListItem      : One employee row returned in the list endpoint
"""

import uuid
from datetime import date

from pydantic import BaseModel, EmailStr


class CreateEmployeeRequest(BaseModel):
    """
    Body for POST /employee/add — admin registers a new employee.
    """
    email: EmailStr
    password: str             # Plain text — will be hashed before storing
    department_name: str
    designation: str
    joined_on: date


class EmployeeListItem(BaseModel):
    """
    One employee row returned by GET /employee/ — admin list view.
    Matches the table columns shown in the UI:
      Email | Designation | Department (name) | Actions
    """
    id: uuid.UUID
    email: str
    full_name: str | None = None
    designation: str | None = None
    department_name: str | None = None
    role: str
    is_active: bool


class UpdateProfileRequest(BaseModel):
    """
    Body for PUT /employee/update-profile — employee updates their own profile.

    Employees can update their display name and profile photo URL.
    Other fields (email, role, department) can only be changed by admins.
    """
    full_name: str
    photo_url: str | None = None  # Optional — leave None to keep existing photo
