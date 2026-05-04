"""
app/ai/handlers/param_helpers.py
================================
Shared helper utilities for ACTION tool execution.

Purpose
-------
Centralize cross-cutting helper logic used by tool executors:
- deterministic LLM extraction calls,
- JSON parsing cleanup,
- UUID extraction/validation,
- role guard helpers.

Why this file exists
--------------------
Without this module, each tool executor would duplicate extraction and RBAC code.
By centralizing these helpers, executors stay small and consistent.

Key rules
---------
- LLM output must be parsed as strict JSON.
- Required IDs should fail fast with clear HTTP 422 errors.
- Role checks should be reusable and explicit (`ensure_admin`, `ensure_superadmin`).
"""

import json
import re
from datetime import date
from typing import Any

from fastapi import HTTPException
from groq import Groq, RateLimitError

from app.core.config import settings
from app.models.employee import Employee

_client = Groq(api_key=settings.GROQ_API_KEY)
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)


def llm_call(system: str, user_msg: str, context: dict, max_tokens: int = 220) -> str:
    """
    Run a deterministic LLM call for parameter extraction.

    Uses fast model by default and falls back to the larger model on rate-limit.
    """
    # Strip internal keys that should not be sent to the LLM
    safe_ctx = {k: v for k, v in context.items() if k != "_history"}
    ctx_str = json.dumps(safe_ctx, indent=2)
    messages = [
        {"role": "system", "content": f"{system}\n\nUser context:\n{ctx_str}"},
        {"role": "user", "content": user_msg},
    ]
    try:
        resp = _client.chat.completions.create(
            model=settings.GROQ_FAST_MODEL,
            messages=messages,
            temperature=0.0,
            max_tokens=max_tokens,
        )
    except RateLimitError:
        resp = _client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.0,
            max_tokens=max_tokens,
        )
    return resp.choices[0].message.content.strip()


def json_from_llm(raw: str) -> dict[str, Any]:
    """Strip optional markdown fences and parse strict JSON output."""
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw).strip()
    if not raw:
        return {}
    # Try to extract a JSON object if the LLM wrapped it in extra text
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def extract_uuid(text: str) -> str | None:
    """Return first UUID found in text, or None if absent."""
    m = _UUID_RE.search(text)
    return m.group(0) if m else None


def extract_required_uuid(message: str, context: dict, key_name: str, prompt: str) -> str:
    """
    Resolve a required UUID from user message or LLM extraction.

    Raises HTTP 422 when the field is still missing.
    """
    maybe_id = extract_uuid(message)
    if maybe_id:
        return maybe_id
    data = json_from_llm(llm_call(prompt, message, context))
    value = data.get(key_name)
    if not value:
        raise HTTPException(status_code=422, detail=f"Missing required field: {key_name}")
    return value


def ensure_admin(user: Employee) -> None:
    """Raise HTTP 403 unless user is admin/superadmin."""
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Only admins can perform this action.")


def ensure_superadmin(user: Employee) -> None:
    """Raise HTTP 403 unless user is superadmin."""
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmins can perform this action.")


def current_month_year() -> tuple[int, int]:
    """Helper for month-scoped attendance queries."""
    today = date.today()
    return today.month, today.year
