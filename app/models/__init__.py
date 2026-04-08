from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


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
