from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# IMPORT ALL MODELS HERE
from .organization import Organization
from .department import Department  
from .employee import Employee
from .refresh_token import RefreshToken
from .project import Project
from .attendance_session import AttendanceSession
from .task_entry import TaskEntry
from .leave_wfh_request import LeaveRequest
from .audit_log import AuditLog
from .holiday import Holiday
from .employee_leave_balance import LeaveBalance
from .leave_policy import LeavePolicy
