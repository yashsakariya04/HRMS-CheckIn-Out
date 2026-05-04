"""
app/ai/classifier.py
====================
Intent classifier for AI chat messages.

Purpose
-------
Convert free-form user text into a structured routing decision:
  - `intent`: ACTION | SQL | CHAT | AMBIGUOUS
  - `confidence`: model confidence score
  - `action_hint`: exact ACTION key (when intent=ACTION)

How it works
------------
1) Build a cache key from normalized message text.
2) Try Redis cache first for fast repeat responses.
3) Call fast model with strict JSON schema instructions.
4) On rate-limit, fall back to larger model.
5) On repeated failure, return safe CHAT fallback.
6) Cache successful classification for a short TTL.

Important design constraints
----------------------------
- `action_hint` values are contract keys consumed by the ACTION tool registry.
- Classifier only decides *what* user wants, not *how* to execute it.
- Execution safety (RBAC, validation, service calls) is handled downstream.
"""

import hashlib
import json
import re

import redis.asyncio as aioredis
from groq import Groq, RateLimitError

from app.core.config import settings

_client = Groq(api_key=settings.GROQ_API_KEY)

_SYSTEM = """You are a strict intent classifier for an HRMS (HR Management System).
Your ONLY job is to output valid JSON. Never explain. Never add text outside JSON.

Output format (always exactly this):
{"intent": "ACTION", "confidence": 0.95, "action_hint": "check_in"}

intent must be one of: ACTION, CHAT, AMBIGUOUS
(SQL is reserved — never use it)

RULES:
- If the user wants to VIEW data about themselves → ACTION
- If the user wants to PERFORM an action → ACTION
- If the user is greeting, thanking, or asking a general question → CHAT
- When in doubt between two action_hints, pick the more specific one
- "show", "view", "check", "what is", "how many" + a data topic → ACTION (view)
- "apply","add", "submit", "request", "take", "need" + a leave/wfh topic → ACTION (apply)
- NEVER classify a VIEW query as an APPLY action

CRITICAL DISAMBIGUATION:
- "show leave balance" / "my leave balance" / "how many leaves" → view_balance (NOT apply_leave)
- "my requests" / "show requests" / "request status" → view_my_requests (NOT apply_leave)
- "apply leave" / "take leave" / "need leave" / "request leave" → apply_leave
- "show my balance" / "leaves left" / "casual leaves" → view_balance
- "check in" / "start my day" → check_in (NOT view_today_session)
- "am i checked in" / "today session" → view_today_session (NOT check_in)
- "my attendance" / "sessions this month" → view_attendance_month
- "average hours" → view_avg_hours
- "team calendar" / "who is on leave" → view_calendar (NOT view_leave_history)
- "my leave history" / "when did i take leave" → view_leave_history (NOT view_calendar)

action_hint must be exactly one of these values (null for CHAT/AMBIGUOUS):

  check_in               user wants to check in / start their workday
  check_out              user wants to check out / end their workday
  view_today_session     user asks about today's attendance session status
  view_attendance_month  user asks about their attendance this month
  view_avg_hours         user asks about their average working hours

  view_tasks_today       user asks what tasks they logged today
  add_task               user wants to add/log a new task
  edit_task              user wants to edit/update an existing task
  delete_task            user wants to delete/remove a task

  apply_leave            user wants to SUBMIT a leave request (not view)
  apply_wfh              user wants to SUBMIT a work-from-home request
  apply_comp_off         user wants to SUBMIT a compensatory off request
  apply_missing_time     user wants to correct a missing checkout time
  view_my_requests       user wants to SEE their existing requests / status
  cancel_request         user wants to cancel a pending request

  view_balance           user wants to SEE their leave balance / remaining leaves
  view_leave_history     user wants to see their past leave history

  list_projects          user asks what projects exist
  list_holidays          user asks about holidays
  view_calendar          user asks about team calendar / who is on leave

  approve_request        admin approves a request
  reject_request         admin rejects a request
  view_all_requests      admin views all team requests
  list_employees         admin lists employees
  add_employee           admin adds a new employee
  deactivate_employee    admin deactivates an employee
  view_employee_balance  admin checks a specific employee's balance
  view_leave_summary     admin views leave summary across team
  view_employee_report   admin views attendance report for an employee
  add_project            admin adds a project
  delete_project         admin deletes a project
  add_holiday            admin adds a holiday
  delete_holiday         admin deletes a holiday
  promote_to_admin       superadmin promotes user to admin
  demote_to_employee     superadmin demotes admin to employee
  list_all_users         superadmin lists all users
"""

_CACHE_TTL = 300


def _cache_key(message: str) -> str:
    h = hashlib.sha256(message.lower().strip().encode()).hexdigest()
    return f"ai:classify:{h}"


def _parse(raw: str) -> dict:
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def _call(model: str, message: str) -> dict:
    resp = _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": message},
        ],
        temperature=0.0,
        max_tokens=80,
    )
    return _parse(resp.choices[0].message.content)


async def classify(message: str, redis: aioredis.Redis | None = None) -> dict:
    if redis:
        try:
            cached = await redis.get(_cache_key(message))
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    result = None
    try:
        result = _call(settings.GROQ_FAST_MODEL, message)
    except RateLimitError:
        try:
            result = _call(settings.GROQ_MODEL, message)
        except RateLimitError:
            return {"intent": "CHAT", "confidence": 0.5, "action_hint": None, "rate_limited": True}
        except Exception:
            return {"intent": "CHAT", "confidence": 0.5, "action_hint": None}
    except Exception:
        return {"intent": "CHAT", "confidence": 0.5, "action_hint": None}

    if redis and result:
        try:
            await redis.setex(_cache_key(message), _CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    return result
