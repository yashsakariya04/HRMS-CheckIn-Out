"""
app/models/employee.py — Department & Employee Database Models
==============================================================
Defines the `department` and `employee` tables.

Non-technical summary:
----------------------
This file describes two database tables:

  Department:
    A group within the company (e.g. "Engineering", "HR", "Sales").
    Each department belongs to one organization.

  Employee:
    Every person who uses the system — both regular employees AND admins.
    The `role` column ("employee" or "admin") controls what they can do.
    There are NO passwords — login is done via Google OAuth only.
    The `google_id` column links the record to the employee's Google account.

Key design decisions:
  - Soft delete: employees are never hard-deleted. Setting `is_active = False`
    deactivates them while preserving all their historical data.
  - Single table for all roles: admins and employees share the same table,
    distinguished only by the `role` column.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey,
    String, TIMESTAMP, text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Department(Base):
    """
    SQLAlchemy ORM model for the `department` table.

    A department groups employees within an organization.
    Department names must be unique within the same organization
    (two orgs can both have a "HR" department, but one org cannot
    have two departments named "HR").
    """
    __tablename__ = "department"

    __table_args__ = (
        # Prevent duplicate department names within the same organization
        UniqueConstraint("organization_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Which company this department belongs to
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Department display name (e.g. "Engineering", "HR")
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


class Employee(Base):
    """
    SQLAlchemy ORM model for the `employee` table.

    Single table for ALL users — both regular employees and admins.
    The `role` column controls permissions:
      - "employee" : Can check in/out, log tasks, submit requests.
      - "admin"    : Can also approve/reject requests, view reports,
                     add employees/projects/holidays.

    Authentication:
      - No passwords stored. Login is via Google OAuth only.
      - `google_id` links to the Google account (our addition).
      - `email` is the primary identifier from Google.

    Soft delete:
      - `is_active = False` deactivates an employee without deleting
        their attendance history, leave records, or task logs.
    """
    __tablename__ = "employee"

    __table_args__ = (
        # Database-level enforcement: role must be one of these two values
        CheckConstraint("role IN ('employee', 'admin')", name="check_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Which company this employee belongs to
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional department assignment (NULL = not assigned to any department)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Primary identifier — comes from Google login, must be unique
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False,
    )

    # Display name — auto-filled from Google on first login, editable after
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # Google's unique user ID — used to link the record to a Google account
    google_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True,
    )

    # Profile photo URL — auto-filled from Google on first login
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Job title / position (e.g. "Software Engineer", "HR Manager")
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # "employee" or "admin" — enforced by CheckConstraint above
    role: Mapped[str] = mapped_column(
        String(20),
        server_default="employee",
        nullable=False,
    )

    # False = deactivated (soft delete). Never hard-delete employees.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )

    # Date the employee joined the company (set on first login if not pre-filled)
    joined_on: Mapped[date | None] = mapped_column(Date)

    # Timestamp of the most recent successful login
    last_login_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
