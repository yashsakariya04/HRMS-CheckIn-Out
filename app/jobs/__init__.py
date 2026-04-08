# app/models/__init__.py
"""
Central import for all SQLAlchemy models.

Importing this package guarantees that every model is registered
with Base.metadata — required for Alembic to detect all tables.

Every time you add a new model file, add its import here.
"""

from app.models.organization import Organization
from app.models.employee import Department, Employee
from app.models.refresh_token import RefreshToken
from app.models.project import Project
from app.models.attendance_session import AttendanceSession
from app.models.task_entry import TaskEntry
from app.models.leave_policy import LeavePolicy
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest
from app.models.holiday import Holiday
from app.models.audit_log import AuditLog

__all__ = [
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