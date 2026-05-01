"""
app/ai/handlers/tool_registry.py
================================
Declarative ACTION tool registry and unified execution pipeline.

What this file does
-------------------
This module is the core of ACTION-intent automation for the AI chatbot.
It converts a classifier `action_hint` into a safe, explicit backend operation.

Instead of large if/elif routing, actions are registered as `ToolSpec` entries:
  - name: logical tool name
  - api_call: endpoint metadata for response/audit visibility
  - min_role: minimum RBAC level (employee/admin/superadmin)
  - executor: async function that performs the operation

High-level flow
---------------
1) `action_handler.handle_action()` resolves `action_hint` in `get_tool_registry()`.
2) It calls `execute_tool(spec, db, user, message, context)`.
3) `execute_tool()` enforces role permission using `_has_role()`.
4) Tool executor parses required params (via `param_helpers`), then calls service layer.
5) Result is normalized to a consistent shape:
     {"response": str, "api_call": str | None, "needs_followup": bool}

Safety model
------------
- Whitelist-only execution: only tools defined in `get_tool_registry()` can run.
- RBAC enforced before execution for every tool.
- LLM is used only for parameter extraction, not arbitrary code/SQL execution.
- Business rules remain in existing service modules (`app/services/*`).

How to add a new ACTION
-----------------------
1) Add a new `action_hint` in `app/ai/classifier.py`.
2) Implement a small executor function here.
3) Register it in `get_tool_registry()` with correct `min_role` and `api_call`.
4) Keep validation/business rules in service layer; keep executor thin.
"""

from dataclasses import dataclass
from datetime import date
from typing import Awaitable, Callable, Literal
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee
from app.models.task_entry import TaskEntry
from app.schemas.add_holiday import SetHoliday
from app.schemas.add_project import ProjectCreate
from app.schemas.add_user import CreateEmployeeRequest
from app.schemas.attendance import CheckInRequest, TaskInput
from app.schemas.request_Emp import RequestCreate
from app.services import (
    add_holiday_service,
    add_project_service,
    add_user_service,
    attendance_service,
    calendar_service,
    leave_service,
    leave_service_Emp,
    reporting_service,
    request_service,
    superadmin_service,
)

from app.ai.handlers.param_helpers import (
    current_month_year,
    ensure_admin,
    ensure_superadmin,
    extract_required_uuid,
    json_from_llm,
    llm_call,
)

ToolResult = dict[str, str | bool | None]
ToolExecutor = Callable[[AsyncSession, Employee, str, dict], Awaitable[ToolResult]]
Role = Literal["employee", "admin", "superadmin"]


@dataclass(frozen=True)
class ToolSpec:
    """Static contract for one AI action tool."""
    name: str
    api_call: str
    min_role: Role
    executor: ToolExecutor


def _has_role(user: Employee, min_role: Role) -> bool:
    """Role hierarchy gate used by the centralized executor."""
    if min_role == "employee":
        return user.role in ("employee", "admin", "superadmin")
    if min_role == "admin":
        return user.role in ("admin", "superadmin")
    return user.role == "superadmin"


async def execute_tool(
    spec: ToolSpec,
    db: AsyncSession,
    user: Employee,
    message: str,
    context: dict,
) -> ToolResult:
    """
    Unified execution path for all ACTION tools.

    Enforces role access and normalizes response fields used by router.
    """
    if not _has_role(user, spec.min_role):
        return {
            "response": f"You do not have permission for `{spec.name}`.",
            "api_call": None,
            "needs_followup": False,
        }
    result = await spec.executor(db, user, message, context)
    if "api_call" not in result:
        result["api_call"] = spec.api_call
    if "needs_followup" not in result:
        result["needs_followup"] = False
    return result


async def _check_in_initial(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Start two-turn check-in by asking for task payload."""
    if context["checked_in_today"]:
        return {"response": f"You already checked in at {context['check_in_at']}.", "api_call": None, "needs_followup": False}
    return {
        "response": "What are you working on today? Please share project, task description, and hours.",
        "api_call": None,
        "needs_followup": True,
    }


async def checkin_followup(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Complete two-turn check-in after collecting project/task/hours."""
    data = json_from_llm(
        llm_call(
            """Extract check-in task JSON:
{"project_id":"uuid","description":"text","hours":4}
Use active_projects from context for project_id. If missing fields:
{"error":"what is missing"}""",
            message,
            context,
        )
    )
    if "error" in data:
        return {"response": f"I need more details: {data['error']}", "api_call": None, "needs_followup": True}

    body = CheckInRequest(
        tasks=[
            TaskInput(
                project_id=uuid.UUID(data["project_id"]),
                description=data["description"],
                hours=float(data["hours"]),
            )
        ]
    )
    session = await attendance_service.check_in(db, user.id, user.organization_id, body)
    return {
        "response": f"Checked you in at {session.check_in_at.strftime('%I:%M %p')} and logged your task.",
        "api_call": "POST /attendance/check-in",
        "needs_followup": False,
    }


async def _check_out(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Check out current user from today's open attendance session."""
    session = await attendance_service.check_out(db, user.id)
    return {"response": f"Checked you out at {session.check_out_at.strftime('%I:%M %p')}. Total: {session.total_hours}h."}


async def _view_today_session(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Return a human summary of today's session state."""
    session = await attendance_service.get_today_session(db, user.id)
    if not session:
        return {"response": "No session found for today yet."}
    if session.check_out_at:
        return {"response": f"Today's session: checked in at {session.check_in_at.strftime('%I:%M %p')} and checked out at {session.check_out_at.strftime('%I:%M %p')}."}
    return {"response": f"You're currently checked in since {session.check_in_at.strftime('%I:%M %p')}."}


async def _view_attendance_month(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Return monthly attendance count for current user."""
    month, year = current_month_year()
    sessions = await attendance_service.get_sessions_for_month(db, user.id, month, year)
    return {"response": f"You have {len(sessions)} attendance session(s) this month."}


async def _view_avg_hours(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Compute average checked-out hours for current month."""
    month, year = current_month_year()
    result = await db.execute(
        select(func.avg(AttendanceSession.total_hours)).where(
            AttendanceSession.employee_id == user.id,
            func.extract("year", AttendanceSession.session_date) == year,
            func.extract("month", AttendanceSession.session_date) == month,
            AttendanceSession.check_out_at.isnot(None),
        )
    )
    avg = result.scalar()
    return {"response": f"Your average daily hours this month: {round(float(avg), 2) if avg else 0.0}h."}


async def _view_tasks_today(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """List tasks from today's attendance session."""
    session = await attendance_service.get_today_session(db, user.id)
    if not session:
        return {"response": "No tasks yet today because you have no session."}
    tasks = (
        await db.execute(
            select(TaskEntry)
            .where(TaskEntry.session_id == session.id)
            .order_by(TaskEntry.sort_order, TaskEntry.created_at)
        )
    ).scalars().all()
    if not tasks:
        return {"response": "No tasks logged for today yet."}
    lines = [f"{len(tasks)} task(s) today:"] + [f"- {t.description} ({float(t.hours_logged)}h)" for t in tasks[:7]]
    return {"response": "\n".join(lines)}


async def _add_task(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Parse task payload and append it to today's session."""
    data = json_from_llm(
        llm_call(
            """Extract JSON for adding task:
{"project_id":"uuid","description":"text","hours":2.5}
Use active_projects from context.""",
            message,
            context,
        )
    )
    session = await attendance_service.get_today_session(db, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="No session found for today. Please check in first.")
    existing_count = len((await db.execute(select(TaskEntry).where(TaskEntry.session_id == session.id))).scalars().all())
    task = TaskEntry(
        session_id=session.id,
        project_id=uuid.UUID(data["project_id"]),
        employee_id=user.id,
        description=data["description"],
        hours_logged=float(data["hours"]),
        sort_order=existing_count,
    )
    db.add(task)
    await db.commit()
    return {"response": "Task added to today's session."}


async def _edit_task(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Edit one existing task owned by current user."""
    data = json_from_llm(
        llm_call('Extract JSON {"task_id":"uuid","project_id":"uuid","description":"text","hours":3}', message, context)
    )
    task = (
        await db.execute(
            select(TaskEntry).where(
                TaskEntry.id == uuid.UUID(data["task_id"]),
                TaskEntry.employee_id == user.id,
            )
        )
    ).scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    task.project_id = uuid.UUID(data["project_id"])
    task.description = data["description"]
    task.hours_logged = float(data["hours"])
    await db.commit()
    return {"response": "Task updated.", "api_call": f"PUT /tasks/{data['task_id']}"}


async def _delete_task(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Delete one task if session still has at least one remaining task."""
    task_id = extract_required_uuid(message, context, "task_id", 'Extract {"task_id":"uuid"}')
    task = (
        await db.execute(
            select(TaskEntry).where(
                TaskEntry.id == uuid.UUID(task_id),
                TaskEntry.employee_id == user.id,
            )
        )
    ).scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    task_count = len((await db.execute(select(TaskEntry).where(TaskEntry.session_id == task.session_id))).scalars().all())
    if task_count < 2:
        raise HTTPException(status_code=409, detail="Cannot delete the only task on this session.")
    await db.delete(task)
    await db.commit()
    return {"response": "Task deleted.", "api_call": f"DELETE /tasks/{task_id}"}


async def _apply_request(request_type: str, db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Shared request creator for leave/WFH/comp-off/missing-time."""
    data = json_from_llm(
        llm_call(
            f"""Extract request JSON for type {request_type}.
Return JSON with from_date,to_date,reason,checkout_time(optional HH:MM only for missing_time).
Example: {{"from_date":"2026-05-01","to_date":"2026-05-01","reason":"reason","checkout_time":"18:30"}}
If ambiguous, return {{"error":"..."}}.""",
            message,
            context,
        )
    )
    if "error" in data:
        return {"response": f"I need more details: {data['error']}", "api_call": None, "needs_followup": True}
    req = await request_service.create_request(
        db,
        user,
        RequestCreate(
            request_type=request_type,
            from_date=date.fromisoformat(data["from_date"]),
            to_date=date.fromisoformat(data["to_date"]),
            reason=data["reason"],
            checkout_time=data.get("checkout_time"),
        ),
    )
    return {"response": f"{request_type.replace('_', ' ').title()} request submitted with status {req.status}."}


async def _apply_leave(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Create leave request."""
    return await _apply_request("leave", db, user, message, context)


async def _apply_wfh(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Create WFH request."""
    return await _apply_request("wfh", db, user, message, context)


async def _apply_comp_off(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Create comp-off request."""
    return await _apply_request("comp_off", db, user, message, context)


async def _apply_missing_time(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Create missing-time correction request."""
    return await _apply_request("missing_time", db, user, message, context)


async def _view_my_requests(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """List current user's requests with short preview."""
    rows = await request_service.get_user_requests(db, user)
    if not rows:
        return {"response": "You have no requests."}
    preview = [f"- {r.request_type}: {r.status} ({r.from_date} to {r.to_date})" for r in rows[:7]]
    return {"response": f"You have {len(rows)} request(s):\n" + "\n".join(preview)}


async def _cancel_request(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Cancel one request owned by current user."""
    request_id = extract_required_uuid(message, context, "request_id", 'Extract {"request_id":"uuid"}')
    await request_service.cancel_request(db, request_id, user)
    return {"response": "Request cancelled.", "api_call": f"DELETE /requests/{request_id}"}


async def _view_balance(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Show balance values from already-built context."""
    casual = context["leave_balance"]["casual"]
    comp_off = context["leave_balance"]["comp_off"]
    return {"response": f"Your leave balance: casual {casual}, comp-off {comp_off}."}


async def _view_leave_history(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Show brief leave history summary for current user."""
    data = await leave_service_Emp.get_my_leaves(db, user.id)
    return {"response": f"Leave history loaded. Current month leave days: {len(data.current_month.dates)}."}


async def _view_calendar(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Load org leave/WFH calendar for current month."""
    today = date.today()
    cal = await calendar_service.get_monthly_calendar(db, user.organization_id, today.month, today.year)
    return {"response": f"Team calendar loaded for {cal.month}/{cal.year} with {len(cal.data)} day(s) having leave/WFH entries."}


async def _list_projects(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Return active projects count."""
    projects = await add_project_service.get_projects(db)
    return {"response": f"There are {len(projects)} active project(s)."}


async def _list_holidays(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Return holiday record count."""
    holidays = await add_holiday_service.get_holidays(db)
    return {"response": f"There are {len(holidays)} holiday record(s)."}


async def _approve_request(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin action to approve one request."""
    ensure_admin(user)
    request_id = extract_required_uuid(message, context, "request_id", 'Extract {"request_id":"uuid"}')
    req = await request_service.approve_request(db, request_id, user)
    return {"response": f"Approved {req.request_type} request for {req.employee_name}.", "api_call": f"PATCH /requests/{request_id}/approve"}


async def _reject_request(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin action to reject one request with optional note."""
    ensure_admin(user)
    data = json_from_llm(llm_call('Extract {"request_id":"uuid","note":"optional reason"}', message, context))
    request_id = data.get("request_id") or extract_required_uuid(message, context, "request_id", 'Extract {"request_id":"uuid"}')
    await request_service.reject_request(db, request_id, user, data.get("note"))
    return {"response": "Request rejected.", "api_call": f"PATCH /requests/{request_id}/reject"}


async def _view_all_requests(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin summary of all requests."""
    ensure_admin(user)
    rows = await leave_service.get_all_requests(db)
    pending = len([r for r in rows if r["status"] == "pending"])
    return {"response": f"Found {len(rows)} total requests ({pending} pending)."}


async def _view_employee_balance(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin lookup for specific employee's request/balance context."""
    ensure_admin(user)
    emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
    target = (await db.execute(select(Employee).where(Employee.id == uuid.UUID(emp_id)))).scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Employee not found.")
    reqs = await request_service.get_user_requests(db, target)
    return {"response": f"Loaded employee request/balance context for {target.email}. Total requests: {len(reqs)}.", "api_call": f"GET /balances/{emp_id}"}


async def _view_leave_summary(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin leave-summary overview."""
    ensure_admin(user)
    rows = await leave_service.get_leave_summary(db)
    return {"response": f"Leave summary loaded for {len(rows)} employee(s)."}


async def _view_employee_report(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin attendance report summary for one employee."""
    ensure_admin(user)
    emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
    report = await reporting_service.get_employee_report(uuid.UUID(emp_id), False, db)
    return {"response": f"Report loaded with {len(report.records)} attendance record(s).", "api_call": f"GET /reporting/{emp_id}"}


async def _list_employees(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin list of active employees."""
    ensure_admin(user)
    rows = await add_user_service.list_employees(db)
    return {"response": f"Found {len(rows)} active employee(s)."}


async def _add_employee(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin create employee from extracted payload."""
    ensure_admin(user)
    data = json_from_llm(llm_call('Extract {"email":"...","department_name":"...","designation":"..."}', message, context))
    emp = await add_user_service.create_employee(CreateEmployeeRequest(**data), db)
    return {"response": f"Employee added: {emp.email}."}


async def _deactivate_employee(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin deactivate employee."""
    ensure_admin(user)
    emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
    await add_user_service.delete_employee(uuid.UUID(emp_id), db)
    return {"response": "Employee deactivated.", "api_call": f"DELETE /employee/{emp_id}"}


async def _add_project(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin create project."""
    ensure_admin(user)
    data = json_from_llm(llm_call('Extract {"name":"project name","description":"optional"}', message, context))
    project = await add_project_service.create_project(ProjectCreate(**data), db)
    return {"response": f"Project created: {project.name}."}


async def _delete_project(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin delete project."""
    ensure_admin(user)
    project_id = extract_required_uuid(message, context, "project_id", 'Extract {"project_id":"uuid"}')
    await add_project_service.delete_project(uuid.UUID(project_id), db)
    return {"response": "Project deleted.", "api_call": f"DELETE /project/{project_id}"}


async def _add_holiday(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin create holiday."""
    ensure_admin(user)
    data = json_from_llm(llm_call('Extract {"name":"...","type":"public|internal|other","date":"YYYY-MM-DD"}', message, context))
    holiday = await add_holiday_service.create_holiday(SetHoliday(**data), db)
    return {"response": f"Holiday added: {holiday.name} on {holiday.holiday_date}."}


async def _delete_holiday(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin delete holiday."""
    ensure_admin(user)
    holiday_id = extract_required_uuid(message, context, "holiday_id", 'Extract {"holiday_id":"uuid"}')
    await add_holiday_service.delete_holiday(uuid.UUID(holiday_id), db)
    return {"response": "Holiday deleted.", "api_call": f"DELETE /holiday/{holiday_id}"}


async def _promote_to_admin(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Superadmin promote employee to admin."""
    ensure_superadmin(user)
    emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
    result = await superadmin_service.promote_to_admin(uuid.UUID(emp_id), db)
    return {"response": result["message"], "api_call": f"PATCH /superadmin/users/{emp_id}/promote"}


async def _demote_to_employee(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Superadmin demote admin to employee."""
    ensure_superadmin(user)
    emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
    result = await superadmin_service.demote_to_employee(uuid.UUID(emp_id), db)
    return {"response": result["message"], "api_call": f"PATCH /superadmin/users/{emp_id}/demote"}


async def _list_all_users(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Superadmin list all users."""
    ensure_superadmin(user)
    rows = await superadmin_service.list_all_users(db)
    return {"response": f"Found {len(rows)} user(s) across all roles."}


def get_tool_registry() -> dict[str, ToolSpec]:
    """
    Master ACTION whitelist.

    `action_hint` from classifier must map to one of these entries.
    """
    return {
        "check_in": ToolSpec("check_in", "POST /attendance/check-in", "employee", _check_in_initial),
        "check_out": ToolSpec("check_out", "PATCH /attendance/check-out", "employee", _check_out),
        "view_today_session": ToolSpec("view_today_session", "GET /attendance/today", "employee", _view_today_session),
        "view_attendance_month": ToolSpec("view_attendance_month", "GET /attendance/sessions", "employee", _view_attendance_month),
        "view_avg_hours": ToolSpec("view_avg_hours", "GET /attendance/avg-hours", "employee", _view_avg_hours),
        "view_tasks_today": ToolSpec("view_tasks_today", "GET /tasks/today", "employee", _view_tasks_today),
        "add_task": ToolSpec("add_task", "POST /tasks", "employee", _add_task),
        "edit_task": ToolSpec("edit_task", "PUT /tasks/{id}", "employee", _edit_task),
        "delete_task": ToolSpec("delete_task", "DELETE /tasks/{id}", "employee", _delete_task),
        "apply_leave": ToolSpec("apply_leave", "POST /requests", "employee", _apply_leave),
        "apply_wfh": ToolSpec("apply_wfh", "POST /requests", "employee", _apply_wfh),
        "apply_comp_off": ToolSpec("apply_comp_off", "POST /requests", "employee", _apply_comp_off),
        "apply_missing_time": ToolSpec("apply_missing_time", "POST /requests", "employee", _apply_missing_time),
        "view_my_requests": ToolSpec("view_my_requests", "GET /requests", "employee", _view_my_requests),
        "cancel_request": ToolSpec("cancel_request", "DELETE /requests/{id}", "employee", _cancel_request),
        "view_balance": ToolSpec("view_balance", "GET /balances/me", "employee", _view_balance),
        "view_leave_history": ToolSpec("view_leave_history", "GET /leaves/me", "employee", _view_leave_history),
        "view_calendar": ToolSpec("view_calendar", "GET /calendar", "employee", _view_calendar),
        "list_projects": ToolSpec("list_projects", "GET /project/", "employee", _list_projects),
        "list_holidays": ToolSpec("list_holidays", "GET /holiday/", "employee", _list_holidays),
        "approve_request": ToolSpec("approve_request", "PATCH /requests/{id}/approve", "admin", _approve_request),
        "reject_request": ToolSpec("reject_request", "PATCH /requests/{id}/reject", "admin", _reject_request),
        "view_all_requests": ToolSpec("view_all_requests", "GET /requests/requests", "admin", _view_all_requests),
        "view_employee_balance": ToolSpec("view_employee_balance", "GET /balances/{emp_id}", "admin", _view_employee_balance),
        "view_leave_summary": ToolSpec("view_leave_summary", "GET /leaves/summary", "admin", _view_leave_summary),
        "view_employee_report": ToolSpec("view_employee_report", "GET /reporting/{emp_id}", "admin", _view_employee_report),
        "list_employees": ToolSpec("list_employees", "GET /employee/", "admin", _list_employees),
        "add_employee": ToolSpec("add_employee", "POST /employee/add", "admin", _add_employee),
        "deactivate_employee": ToolSpec("deactivate_employee", "DELETE /employee/{id}", "admin", _deactivate_employee),
        "add_project": ToolSpec("add_project", "POST /project/add", "admin", _add_project),
        "delete_project": ToolSpec("delete_project", "DELETE /project/{id}", "admin", _delete_project),
        "add_holiday": ToolSpec("add_holiday", "POST /holiday/add", "admin", _add_holiday),
        "delete_holiday": ToolSpec("delete_holiday", "DELETE /holiday/{id}", "admin", _delete_holiday),
        "promote_to_admin": ToolSpec("promote_to_admin", "PATCH /superadmin/users/{id}/promote", "superadmin", _promote_to_admin),
        "demote_to_employee": ToolSpec("demote_to_employee", "PATCH /superadmin/users/{id}/demote", "superadmin", _demote_to_employee),
        "list_all_users": ToolSpec("list_all_users", "GET /superadmin/users", "superadmin", _list_all_users),
    }
