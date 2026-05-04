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
import json
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


async def _attempt_checkin(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Try to extract project/task/hours and check in. If anything missing, ask naturally."""
    projects = context.get("active_projects", [])
    projects_str = json.dumps(projects)
    data = json_from_llm(
        llm_call(
            f"""Extract check-in details from the user message.
Active projects: {projects_str}
Match project name to project_id from the list above (fuzzy match is fine).
Return JSON: {{"project_id":"uuid or null","description":"task text or null","hours":number or null}}
If a field is not mentioned, set it to null. Never guess.""",
            message,
            context,
        )
    )

    missing = [k for k in ["project_id", "description", "hours"] if not data.get(k)]

    if missing:
        present = {k: data[k] for k in ["project_id", "description", "hours"] if data.get(k)}
        ask = json_from_llm(
            llm_call(
                f"""The user wants to check in. You have collected: {json.dumps(present)}.
Missing fields: {missing}.
Write a single short natural conversational question to ask for the missing info.
Return JSON: {{"question": "your question here"}}""",
                message,
                context,
            )
        )
        question = ask.get("question") or f"Could you also share your {', '.join(missing)}?"
        # Embed pending tag so action_handler can route the follow-up deterministically
        return {"response": f"{question} [PENDING:check_in]", "api_call": None, "needs_followup": True, "_partial": present}

    return await _do_checkin(db, user, data)


async def _do_checkin(db: AsyncSession, user: Employee, data: dict) -> ToolResult:
    """Execute the actual check-in service call."""
    try:
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
            "response": f"✓ Checked you in at {session.check_in_at.strftime('%I:%M %p')} and logged your task.",
            "api_call": "POST /attendance/check-in",
            "needs_followup": False,
        }
    except ValueError:
        return {"response": "Invalid hours value. Please provide a valid number.", "api_call": None, "needs_followup": True}
    except Exception as e:
        return {"response": f"Check-in failed: {str(e)}", "api_call": None, "needs_followup": True}


async def _check_in_initial(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Entry point for check-in — tries to complete in one turn if all details present."""
    if context.get("checked_in_today"):
        return {"response": f"You're already checked in at {context['check_in_at']}.", "api_call": None, "needs_followup": False}
    return await _attempt_checkin(db, user, message, context)


async def checkin_followup(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Continue multi-turn check-in by merging new info with what was already collected."""
    if context.get("checked_in_today"):
        return {"response": f"You're already checked in at {context['check_in_at']}.", "api_call": None, "needs_followup": False}
    return await _attempt_checkin(db, user, message, context)


async def _check_out(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Check out current user from today's open attendance session."""
    try:
        if not context.get("checked_in_today"):
            return {"response": "You're not checked in yet. Please check in first.", "api_call": None, "needs_followup": False}
        session = await attendance_service.check_out(db, user.id)
        if not session or not session.check_out_at:
            return {"response": "Could not check you out. Please try again.", "api_call": None, "needs_followup": False}
        return {
            "response": f"✓ Checked you out at {session.check_out_at.strftime('%I:%M %p')}. Total: {round(session.total_hours, 2)}h.",
            "api_call": "PATCH /attendance/check-out",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": f"Could not check out: {str(e.detail)}", "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Check-out failed: {str(e)}", "api_call": None, "needs_followup": False}


async def _view_today_session(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Return a human summary of today's session state."""
    try:
        session = await attendance_service.get_today_session(db, user.id)
        if not session:
            return {"response": "No session found for today yet. You haven't checked in.", "api_call": "GET /attendance/today", "needs_followup": False}
        if session.check_out_at:
            duration = (session.check_out_at - session.check_in_at).total_seconds() / 3600
            return {"response": f"📋 Today's session:\n✓ Check-in: {session.check_in_at.strftime('%I:%M %p')}\n✓ Check-out: {session.check_out_at.strftime('%I:%M %p')}\n⏱ Duration: {round(duration, 2)}h", "api_call": "GET /attendance/today", "needs_followup": False}
        return {"response": f"📋 Current session:\n✓ Checked in at {session.check_in_at.strftime('%I:%M %p')}\n⏱ Still active", "api_call": "GET /attendance/today", "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to get session: {str(e)}", "api_call": None, "needs_followup": False}

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
    try:
        session = await attendance_service.get_today_session(db, user.id)
        if not session:
            return {"response": "No session found. Please check in first to add tasks.", "api_call": None, "needs_followup": False}
        
        data = json_from_llm(
            llm_call(
                """Extract JSON for adding task:
{"project_id":"uuid or project name","description":"detailed task description","hours":2.5}
Use active_projects from context for matching.""",
                message,
                context,
            )
        )
        
        # Validate required fields
        if not data.get("description") or not data.get("hours"):
            return {"response": "I need both task description and hours worked.", "api_call": None, "needs_followup": True}
        
        try:
            hours = float(data["hours"])
            if hours <= 0 or hours > 24:
                return {"response": "Please provide valid hours (0-24 hours per day).", "api_call": None, "needs_followup": True}
        except (ValueError, TypeError):
            return {"response": "Hours must be a valid number.", "api_call": None, "needs_followup": True}
        
        existing_count = len((await db.execute(select(TaskEntry).where(TaskEntry.session_id == session.id))).scalars().all())
        task = TaskEntry(
            session_id=session.id,
            project_id=uuid.UUID(data["project_id"]),
            description=data["description"],
            hours_logged=hours,
            sort_order=existing_count,
        )
        db.add(task)
        await db.commit()
        return {
            "response": f"✓ Task added: '{data['description']}' ({hours}h)",
            "api_call": "POST /tasks",
            "needs_followup": False,
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to add task: {str(e)}", "api_call": None, "needs_followup": False}


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


async def _apply_request(request_type: str, db: AsyncSession, user: Employee, message: str, context: dict, history: list = None) -> ToolResult:
    """Multi-turn request creator for leave/WFH/comp-off/missing-time."""
    try:
        type_label = request_type.replace('_', ' ').title()
        is_single_day = request_type in ("comp_off", "missing_time")
        needs_checkout = request_type == "missing_time"
        today = context.get("current_date", str(date.today()))

        # Merge full conversation so LLM can pick up data from any prior turn
        conversation = ""
        if history:
            for turn in history:
                conversation += f"{turn['role'].upper()}: {turn['content']}\n"
        conversation += f"USER: {message}"

        if is_single_day:
            prompt = f"""Today is {today}. Extract details for a {request_type} request from the conversation below.
Return ONLY this JSON (use null for missing fields, never guess):
{{"date":"YYYY-MM-DD","reason":"text"{',"checkout_time":"HH:MM"' if needs_checkout else ''}}}

Conversation:
{conversation}"""
        else:
            prompt = f"""Today is {today}. Extract details for a {request_type} request from the conversation below.
Return ONLY this JSON (use null for missing fields, never guess):
{{"from_date":"YYYY-MM-DD","to_date":"YYYY-MM-DD","reason":"text"}}

Conversation:
{conversation}"""

        data = json_from_llm(llm_call(prompt, message, context, max_tokens=120))

        # Normalize single-day types
        if is_single_day and data.get("date"):
            data["from_date"] = data["date"]
            data["to_date"] = data["date"]

        # Collect missing fields
        missing = []
        if not data.get("from_date"):
            missing.append("date" if is_single_day else "start date")
        if not is_single_day and not data.get("to_date"):
            missing.append("end date")
        if not data.get("reason"):
            missing.append("reason")
        if needs_checkout and not data.get("checkout_time"):
            missing.append("checkout time (e.g. 18:30)")

        if missing:
            collected = {k: v for k, v in data.items() if v and k != "date"}
            ask = json_from_llm(
                llm_call(
                    f"""User wants a {type_label} request. Collected so far: {json.dumps(collected)}.
Missing: {missing}. Write one short natural question for the missing info only.
Return JSON: {{"question": "..."}}""",
                    message, context,
                )
            )
            question = ask.get("question") or f"Could you share your {', '.join(missing)}?"
            # Embed pending tag so action_handler routes the follow-up deterministically
            return {"response": f"{question} [PENDING:{request_type}]", "api_call": None, "needs_followup": True}

        # Parse dates
        try:
            from_date = date.fromisoformat(data["from_date"])
            to_date = date.fromisoformat(data["to_date"])
        except (ValueError, KeyError):
            return {"response": "Please provide dates in YYYY-MM-DD format (e.g. 2025-08-01).", "api_call": None, "needs_followup": True}

        if from_date > to_date:
            return {"response": "Start date cannot be after end date.", "api_call": None, "needs_followup": True}

        if request_type in ("leave", "wfh") and from_date < date.today():
            return {"response": "Leave and WFH requests must be for today or a future date.", "api_call": None, "needs_followup": True}

        req = await request_service.create_request(
            db, user,
            RequestCreate(
                request_type=request_type,
                from_date=from_date,
                to_date=to_date,
                reason=data["reason"],
                checkout_time=data.get("checkout_time"),
            ),
        )
        days = (to_date - from_date).days + 1
        return {
            "response": f"✓ {type_label} request submitted for {days} day(s) ({from_date} to {to_date}). Status: {req.status}",
            "api_call": "POST /requests",
            "needs_followup": False,
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Request failed: {str(e)}", "api_call": None, "needs_followup": False}


async def _apply_leave(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    return await _apply_request("leave", db, user, message, context, context.get("_history"))


async def _apply_wfh(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    return await _apply_request("wfh", db, user, message, context, context.get("_history"))


async def _apply_comp_off(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    return await _apply_request("comp_off", db, user, message, context, context.get("_history"))


async def _apply_missing_time(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    return await _apply_request("missing_time", db, user, message, context, context.get("_history"))


async def _view_my_requests(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """List current user's requests with details."""
    try:
        rows = await request_service.get_user_requests(db, user)
        if not rows:
            return {"response": "You have no requests yet.", "api_call": "GET /requests", "needs_followup": False}

        pending = [r for r in rows if r.status == "pending"]
        approved = [r for r in rows if r.status == "approved"]
        rejected = [r for r in rows if r.status == "rejected"]

        lines = [f"📋 Your requests ({len(rows)} total):"]
        if pending:
            lines.append(f"\n⏳ Pending ({len(pending)}):")
            for r in pending[:5]:
                lines.append(f"  • {r.request_type.replace('_',' ').title()}: {r.from_date} → {r.to_date} | ID: ...{str(r.id)[-8:]}")
        if approved:
            lines.append(f"\n✓ Approved ({len(approved)}):")
            for r in approved[:3]:
                lines.append(f"  • {r.request_type.replace('_',' ').title()}: {r.from_date} → {r.to_date}")
        if rejected:
            lines.append(f"\n✗ Rejected ({len(rejected)}):")
            for r in rejected[:3]:
                note = f" | Note: {r.rejection_note}" if r.rejection_note else ""
                lines.append(f"  • {r.request_type.replace('_',' ').title()}: {r.from_date} → {r.to_date}{note}")

        return {"response": "\n".join(lines), "api_call": "GET /requests", "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to load requests: {str(e)}", "api_call": None, "needs_followup": False}


async def _cancel_request(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Cancel one pending request owned by current user."""
    try:
        request_id = extract_required_uuid(message, context, "request_id", 'Extract {"request_id":"uuid"}')
        await request_service.cancel_request(db, request_id, user)
        return {
            "response": "✓ Request cancelled successfully.",
            "api_call": f"DELETE /requests/{request_id}",
            "needs_followup": False,
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to cancel request: {str(e)}", "api_call": None, "needs_followup": False}


async def _view_balance(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Show balance values from already-built context."""
    try:
        casual = context["leave_balance"]["casual"]
        comp_off = context["leave_balance"]["comp_off"]
        return {
            "response": f"📊 Your leave balance:\n  • Casual: {casual} day(s)\n  • Comp-off: {comp_off} day(s)",
            "api_call": "GET /balances/me",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load balance: {str(e)}", "api_call": None, "needs_followup": False}


async def _view_leave_history(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Show brief leave history summary for current user."""
    try:
        data = await leave_service_Emp.get_my_leaves(db, user.id)
        current_month_days = len(data.current_month.dates) if hasattr(data, 'current_month') else 0
        return {
            "response": f"📅 Leave history:\n  • This month: {current_month_days} day(s)",
            "api_call": "GET /leaves/me",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load leave history: {str(e)}", "api_call": None, "needs_followup": False}


async def _view_calendar(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Load org leave/WFH calendar for current month."""
    try:
        today = date.today()
        cal = await calendar_service.get_monthly_calendar(db, user.organization_id, today.month, today.year)
        entries = len(cal.data) if hasattr(cal, 'data') else 0
        return {
            "response": f"📆 Team calendar for {cal.month}/{cal.year}: {entries} day(s) with leave/WFH entries",
            "api_call": "GET /calendar",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load calendar: {str(e)}", "api_call": None, "needs_followup": False}


async def _list_projects(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Return active projects count."""
    try:
        projects = await add_project_service.get_projects(db)
        return {
            "response": f"📌 There are {len(projects)} active project(s) available",
            "api_call": "GET /project/",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load projects: {str(e)}", "api_call": None, "needs_followup": False}


async def _list_holidays(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Return holiday record count."""
    try:
        holidays = await add_holiday_service.get_holidays(db)
        return {
            "response": f"🎉 There are {len(holidays)} holiday record(s) on the calendar",
            "api_call": "GET /holiday/",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load holidays: {str(e)}", "api_call": None, "needs_followup": False}


async def _approve_request(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin action to approve one request."""
    try:
        ensure_admin(user)
        request_id = extract_required_uuid(message, context, "request_id", 'Extract {"request_id":"uuid"}')
        req = await request_service.approve_request(db, request_id, user)
        return {
            "response": f"✓ Approved {req.request_type.replace('_', ' ').title()} request for {req.employee_name}.",
            "api_call": f"PATCH /requests/{request_id}/approve",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to approve request: {str(e)}", "api_call": None, "needs_followup": False}


async def _reject_request(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin action to reject one request with optional note."""
    try:
        ensure_admin(user)
        data = json_from_llm(llm_call('Extract {"request_id":"uuid","note":"optional reason"}', message, context))
        request_id = data.get("request_id") or extract_required_uuid(message, context, "request_id", 'Extract {"request_id":"uuid"}')
        req = await request_service.reject_request(db, request_id, user, data.get("note"))
        return {
            "response": f"✓ Rejected {req.request_type.replace('_', ' ').title()} request.",
            "api_call": f"PATCH /requests/{request_id}/reject",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to reject request: {str(e)}", "api_call": None, "needs_followup": False}


async def _view_all_requests(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin summary of all requests."""
    try:
        ensure_admin(user)
        rows = await leave_service.get_all_requests(db)
        pending = len([r for r in rows if r["status"] == "pending"])
        approved = len([r for r in rows if r["status"] == "approved"])
        rejected = len([r for r in rows if r["status"] == "rejected"])
        
        summary = f"📋 All requests summary:\n"
        summary += f"  • Total: {len(rows)}\n"
        summary += f"  ✓ Approved: {approved}\n"
        summary += f"  ⏳ Pending: {pending}\n"
        summary += f"  ✗ Rejected: {rejected}"
        
        return {"response": summary, "api_call": "GET /requests/requests", "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to load requests: {str(e)}", "api_call": None, "needs_followup": False}


async def _view_employee_balance(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin lookup for specific employee's request/balance context."""
    try:
        ensure_admin(user)
        emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
        target = (await db.execute(select(Employee).where(Employee.id == uuid.UUID(emp_id)))).scalars().first()
        if not target:
            return {"response": "Employee not found.", "api_call": None, "needs_followup": False}
        
        reqs = await request_service.get_user_requests(db, target)
        return {
            "response": f"👤 {target.email}:\n  • Total requests: {len(reqs)}\n  • Active: Yes",
            "api_call": f"GET /balances/{emp_id}",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load employee balance: {str(e)}", "api_call": None, "needs_followup": False}


async def _view_leave_summary(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin leave-summary overview."""
    try:
        ensure_admin(user)
        rows = await leave_service.get_leave_summary(db)
        return {
            "response": f"📊 Leave summary for {len(rows)} employee(s) loaded successfully",
            "api_call": "GET /leaves/summary",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load leave summary: {str(e)}", "api_call": None, "needs_followup": False}


async def _view_employee_report(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin attendance report summary for one employee."""
    try:
        ensure_admin(user)
        emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
        report = await reporting_service.get_employee_report(uuid.UUID(emp_id), False, db)
        records = len(report.records) if hasattr(report, 'records') else 0
        return {
            "response": f"📈 Attendance report: {records} record(s) found",
            "api_call": f"GET /reporting/{emp_id}",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load report: {str(e)}", "api_call": None, "needs_followup": False}


async def _list_employees(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin list of active employees."""
    try:
        ensure_admin(user)
        rows = await add_user_service.list_employees(db)
        return {
            "response": f"👥 Found {len(rows)} active employee(s)",
            "api_call": "GET /employee/",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load employees: {str(e)}", "api_call": None, "needs_followup": False}


async def _add_employee(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin create employee from extracted payload."""
    try:
        ensure_admin(user)
        data = json_from_llm(llm_call('Extract {"email":"user@company.com","department_name":"HR","designation":"Manager"}', message, context))
        
        if not data.get("email"):
            return {"response": "Email is required to add an employee.", "api_call": None, "needs_followup": True}
        
        emp = await add_user_service.create_employee(CreateEmployeeRequest(**data), db)
        return {
            "response": f"✓ Employee added: {emp.email}",
            "api_call": "POST /employee/add",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to add employee: {str(e)}", "api_call": None, "needs_followup": False}


async def _deactivate_employee(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin deactivate employee."""
    try:
        ensure_admin(user)
        emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
        emp = await add_user_service.delete_employee(uuid.UUID(emp_id), db)
        return {
            "response": f"✓ Employee deactivated: {emp.email}",
            "api_call": f"DELETE /employee/{emp_id}",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to deactivate employee: {str(e)}", "api_call": None, "needs_followup": False}
    return {"response": "Employee deactivated.", "api_call": f"DELETE /employee/{emp_id}"}


async def _add_project(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin create project."""
    try:
        ensure_admin(user)
        data = json_from_llm(llm_call('Extract {"name":"project name","description":"optional description"}', message, context))
        
        if not data.get("name"):
            return {"response": "Project name is required.", "api_call": None, "needs_followup": True}
        
        project = await add_project_service.create_project(ProjectCreate(**data), db)
        return {
            "response": f"✓ Project created: {project.name}",
            "api_call": "POST /project/add",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to create project: {str(e)}", "api_call": None, "needs_followup": False}


async def _delete_project(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin delete project."""
    try:
        ensure_admin(user)
        project_id = extract_required_uuid(message, context, "project_id", 'Extract {"project_id":"uuid"}')
        await add_project_service.delete_project(uuid.UUID(project_id), db)
        return {
            "response": "✓ Project deleted successfully",
            "api_call": f"DELETE /project/{project_id}",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to delete project: {str(e)}", "api_call": None, "needs_followup": False}


async def _add_holiday(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin create holiday."""
    try:
        ensure_admin(user)
        data = json_from_llm(llm_call('Extract {"name":"holiday name","type":"public|internal|other","date":"YYYY-MM-DD"}', message, context))
        
        if not all(k in data for k in ["name", "type", "date"]):
            return {"response": "Please provide holiday name, type (public/internal/other), and date (YYYY-MM-DD).", "api_call": None, "needs_followup": True}
        
        holiday = await add_holiday_service.create_holiday(SetHoliday(**data), db)
        return {
            "response": f"✓ Holiday added: {holiday.name} on {holiday.holiday_date}",
            "api_call": "POST /holiday/add",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to add holiday: {str(e)}", "api_call": None, "needs_followup": False}


async def _delete_holiday(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Admin delete holiday."""
    try:
        ensure_admin(user)
        holiday_id = extract_required_uuid(message, context, "holiday_id", 'Extract {"holiday_id":"uuid"}')
        await add_holiday_service.delete_holiday(uuid.UUID(holiday_id), db)
        return {
            "response": "✓ Holiday deleted successfully",
            "api_call": f"DELETE /holiday/{holiday_id}",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to delete holiday: {str(e)}", "api_call": None, "needs_followup": False}


async def _promote_to_admin(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Superadmin promote employee to admin."""
    try:
        ensure_superadmin(user)
        emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
        result = await superadmin_service.promote_to_admin(uuid.UUID(emp_id), db)
        return {
            "response": f"✓ {result['message']}",
            "api_call": f"PATCH /superadmin/users/{emp_id}/promote",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to promote user: {str(e)}", "api_call": None, "needs_followup": False}


async def _demote_to_employee(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Superadmin demote admin to employee."""
    try:
        ensure_superadmin(user)
        emp_id = extract_required_uuid(message, context, "employee_id", 'Extract {"employee_id":"uuid"}')
        result = await superadmin_service.demote_to_employee(uuid.UUID(emp_id), db)
        return {
            "response": f"✓ {result['message']}",
            "api_call": f"PATCH /superadmin/users/{emp_id}/demote",
            "needs_followup": False
        }
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Failed to demote user: {str(e)}", "api_call": None, "needs_followup": False}


async def _list_all_users(db: AsyncSession, user: Employee, message: str, context: dict) -> ToolResult:
    """Superadmin list all users."""
    try:
        ensure_superadmin(user)
        rows = await superadmin_service.list_all_users(db)
        return {
            "response": f"👥 Found {len(rows)} user(s) across all roles",
            "api_call": "GET /superadmin/users",
            "needs_followup": False
        }
    except Exception as e:
        return {"response": f"Failed to load users: {str(e)}", "api_call": None, "needs_followup": False}


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




