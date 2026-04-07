# app/models/__init__.py
"""
Central import for all SQLAlchemy models.
Base is defined here so the partner's models (which import from app.models)
and our own models can share the same metadata.

Every time you add a new model file, add its import here.
Alembic reads this file to discover all tables.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ── Import every model so Alembic can discover all tables ── #
from app.models.organization import Organization          # noqa: E402, F401
from app.models.employee import Department, Employee      # noqa: E402, F401
from app.models.refresh_token import RefreshToken         # noqa: E402, F401
from app.models.project import Project                    # noqa: E402, F401
from app.models.attendance_session import AttendanceSession  # noqa: E402, F401
from app.models.task_entry import TaskEntry               # noqa: E402, F401
from app.models.leave_policy import LeavePolicy           # noqa: E402, F401
from app.models.employee_leave_balance import EmployeeLeaveBalance  # noqa: E402, F401
from app.models.leave_wfh_request import LeaveWFHRequest  # noqa: E402, F401
from app.models.holiday import Holiday                    # noqa: E402, F401
from app.models.audit_log import AuditLog                 # noqa: E402, F401

__all__ = [
    "Base",
    "Organization",
    "Department",
    "Employee",
    "RefreshToken",
    "Project",
    "AttendanceSession",
    "TaskEntry",
    "LeavePolicy",
    "EmployeeLeaveBalance",
    "LeaveWFHRequest",
    "Holiday",
    "AuditLog",
]