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

_SYSTEM = """You are an intent classifier for an HRMS (HR Management System).
Classify the user message into exactly one of these intents:
  ACTION     - user wants to perform an action or view their own data
  SQL        - user wants reports or data about multiple employees / org-wide stats
  CHAT       - greeting, thanks, general conversation, how-to questions
  AMBIGUOUS  - unclear intent

Respond with ONLY valid JSON:
{"intent": "ACTION", "confidence": 0.95, "action_hint": "check_in"}

action_hint must be one of these exact values (use null for non-ACTION intents):

  -- Attendance --
  check_in               "check me in", "start my day"
  check_out              "check me out", "end my day", "log off"
  view_today_session     "am i checked in", "today's session", "my check in time"
  view_attendance_month  "my attendance this month", "my sessions"
  view_avg_hours         "my average hours", "how many hours this month"

  -- Tasks --
  view_tasks_today       "my tasks today", "what did i log today"
  add_task               "add a task", "log a task", "i worked on"
  edit_task              "edit task", "update task", "change task"
  delete_task            "delete task", "remove task"

  -- Requests --
  apply_leave            "apply leave", "take a day off", "i need leave"
  apply_wfh              "work from home", "wfh request", "work remotely"
  apply_comp_off         "comp off", "compensatory off", "worked on holiday"
  apply_missing_time     "missing checkout", "forgot to check out", "correct my time"
  view_my_requests       "my requests", "my leave status", "pending requests"
  cancel_request         "cancel my request", "withdraw request"

  -- Balances & Leaves --
  view_balance           "my leave balance", "how many leaves", "leaves left"
  view_leave_history     "my leave history", "when did i take leave"

  -- Info queries --
  list_projects          "what projects", "show projects", "active projects"
  list_holidays          "holidays", "upcoming holidays", "holiday list"
  view_calendar          "team calendar", "who is on leave", "calendar this month"

  -- Admin: Requests --
  approve_request        "approve request", "approve leave"
  reject_request         "reject request", "reject leave"
  view_all_requests      "all requests", "pending approvals", "team requests"

  -- Admin: Employees --
  list_employees         "list employees", "show team", "all employees"
  add_employee           "add employee", "new employee", "register employee"
  deactivate_employee    "deactivate employee", "remove employee"
  view_employee_balance  "employee balance", "check balance for"
  view_leave_summary     "leave summary", "team leave balances"
  view_employee_report   "attendance report for", "employee report"

  -- Admin: Projects & Holidays --
  add_project            "add project", "create project", "new project"
  delete_project         "delete project", "remove project"
  add_holiday            "add holiday", "new holiday", "mark holiday"
  delete_holiday         "delete holiday", "remove holiday"

  -- Superadmin --
  promote_to_admin       "promote to admin", "make admin"
  demote_to_employee     "demote", "remove admin", "make employee"
  list_all_users         "all users", "list all users"
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
