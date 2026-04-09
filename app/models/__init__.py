"""
app/models/__init__.py — SQLAlchemy Base & Model Registry
==========================================================
Defines the shared DeclarativeBase that all ORM models inherit from,
and imports every model so Alembic (the database migration tool) can
discover them automatically.

Non-technical summary:
----------------------
SQLAlchemy needs a single "Base" class that all database table definitions
extend. This file creates that Base and then imports all models so they
are registered with it.

Alembic reads this file when generating migration scripts — if a model
is not imported here, Alembic won't know about it and won't create the
corresponding database table.

Models registered here (one model = one database table):
  - Organization       : Company/tenant record
  - Employee           : All users (employees + admins)
  - RefreshToken       : Stored refresh tokens for session management
  - Project            : Projects employees log tasks against
  - AttendanceSession  : Daily check-in/check-out records
  - TaskEntry          : Individual tasks logged within a session
  - LeavePolicy        : Leave rules per organization (accrual rates, carry-forward)
  - EmployeeLeaveBalance: Monthly leave balance ledger per employee
  - LeaveWFHRequest    : Leave, WFH, missing-time, and comp-off requests
  - Holiday            : Company holiday calendar
  - AuditLog           : Append-only log of admin actions
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Shared base class for all SQLAlchemy ORM models.

    All models in this project inherit from this Base, which ties them
    to the same metadata registry and allows Alembic to manage migrations.
    """
    pass


# ── Import all models so Alembic can detect them ─────────────────────────────
# Order matters for foreign key dependencies: parent tables first.
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.refresh_token import RefreshToken
from app.models.project import Project
from app.models.attendance_session import AttendanceSession
from app.models.task_entry import TaskEntry
from app.models.leave_policy import LeavePolicy
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest
from app.models.holiday import Holiday
from app.models.audit_log import AuditLog
