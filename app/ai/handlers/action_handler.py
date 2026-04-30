"""
app/ai/handlers/action_handler.py
=================================
Thin ACTION dispatcher for AI chat.

Purpose
-------
This module keeps ACTION routing minimal and readable. It does not contain
business logic for each action. Instead, it delegates execution to the
declarative tool system in `tool_registry.py`.

Responsibilities
----------------
1) Handle the special multi-turn check-in follow-up case from conversation history.
2) Resolve `action_hint` to a registered `ToolSpec`.
3) Delegate execution to centralized `execute_tool()` (RBAC + normalized output).
4) Return safe fallback text if hint is unknown.

Design note
-----------
Keeping this file thin prevents if/elif growth and makes behavior predictable.
All per-action details live in registry executors, and all business rules remain
in service-layer modules.
"""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.handlers.tool_registry import checkin_followup, execute_tool, get_tool_registry
from app.models.employee import Employee


async def handle_action(
    db: AsyncSession,
    user: Employee,
    message: str,
    action_hint: str | None,
    context: dict,
    history: list,
) -> dict:
    """
    Execute ACTION intent by dispatching `action_hint` to a registered tool.

    Flow:
    1) Special-case multi-turn check-in follow-up.
    2) Resolve `action_hint` in the tool registry.
    3) Run centralized executor (RBAC + normalized response shape).
    """
    registry = get_tool_registry()

    if history:
        # If the previous assistant question was check-in follow-up, force that flow
        # even if the current classifier hint differs.
        last_assistant = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), "")
        if "What are you working on today" in last_assistant:
            return await checkin_followup(db, user, message, context)

    spec = registry.get(action_hint or "")
    if not spec:
        return {
            "response": "I can help with attendance, tasks, requests, balance, calendar, and admin actions.",
            "api_call": None,
            "needs_followup": False,
        }
    try:
        return await execute_tool(spec, db, user, message, context)
    except HTTPException as e:
        return {"response": str(e.detail), "api_call": None, "needs_followup": False}
    except Exception as e:
        return {"response": f"Action failed: {str(e)}", "api_call": None, "needs_followup": False}
