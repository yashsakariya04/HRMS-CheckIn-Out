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

from pydantic import BaseModel, EmailStr


class CreateEmployeeRequest(BaseModel):
    """
    Body for POST /employee/add — admin registers a new employee.

    The employee is created with just their email, department, and designation.
    Their name and photo are auto-filled from Google on their first login.
    """
    email: EmailStr           # Must be a valid email — this is their login identity
    department_name: str      # Department name typed manually (e.g. "Full Stack", "HR")
    designation: str          # Job title (e.g. "Software Engineer")


class EmployeeListItem(BaseModel):
    """
    One employee row returned by GET /employee/ — admin list view.
    Matches the table columns shown in the UI:
      Email | Designation | Department (name) | Actions
    """
    id: uuid.UUID
    email: str
    designation: str | None = None
    department_name: str | None = None  # Human-readable name, e.g. "Full Stack"
    is_active: bool                     # False = deactivated (shown as greyed out)


class UpdateProfileRequest(BaseModel):
    """
    Body for PUT /employee/update-profile — employee updates their own profile.

    Employees can update their display name and profile photo URL.
    Other fields (email, role, department) can only be changed by admins.
    """
    full_name: str
    photo_url: str | None = None  # Optional — leave None to keep existing photo
