"""
app/ai/router.py
================
Primary API entrypoint for AI chat: `POST /api/v1/ai/chat`.

What this module does
---------------------
Coordinates the complete request lifecycle for one chat turn:
1) Builds trusted user context.
2) Loads server-side conversation history.
3) Classifies intent and action hint.
4) Routes to the correct handler (`ACTION` / `CHAT` / fallback).
5) Persists the turn in conversation history.
6) Logs audit metadata for observability.
7) Returns a normalized response payload to frontend.

Why this structure
------------------
The router is intentionally orchestration-only. It does not implement business
rules directly; handlers and services are responsible for execution details.

Response shape
--------------
{
  "response": "...",
  "intent": "ACTION|CHAT|...",
  "action": "check_in|...",
  "api_call": "POST /attendance/check-in"|null,
  "session_id": "uuid",
  "needs_followup": true|false
}
"""

import time
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import audit, classifier, context, history
from app.ai.handlers import action_handler, chat_handler
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.redis import get_redis
from app.models.employee import Employee

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatRequest(BaseModel):
    message: str
    session_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    response: str
    intent: str
    action: str | None = None
    api_call: str | None = None
    session_id: uuid.UUID
    needs_followup: bool = False


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: Employee = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    start = time.monotonic()

    # Use existing session or start a new one
    session_id = body.session_id or uuid.uuid4()

    # Build user context (one DB round-trip covers balance + today's session)
    ctx = await context.build_context(db, user)

    # Load server-side history — never trust client-sent history
    hist = await history.load_history(db, session_id)

    # Classify intent — uses fast model + Redis cache + fallback to large model
    classification = await classifier.classify(body.message, redis)
    intent = classification.get("intent", "CHAT")
    confidence = classification.get("confidence", 0.5)
    action_hint = classification.get("action_hint")

    # Both models are rate-limited — return a friendly message immediately
    if classification.get("rate_limited"):
        return ChatResponse(
            response="I'm receiving too many requests right now. Please try again in a minute.",
            intent="CHAT",
            session_id=session_id,
        )

    # Route to correct handler
    if intent == "ACTION":
        result = await action_handler.handle_action(
            db, user, body.message, action_hint, ctx, hist
        )
    elif intent in ("CHAT", "AMBIGUOUS"):
        result = chat_handler.handle_chat(body.message, ctx, hist)
    else:
        # SQL, DOCS, MULTI_STEP — Phase 2 & 3, friendly fallback for now
        result = {
            "response": "That type of query is coming soon! For now I can help you check in/out, apply leave, and view your balance.",
            "api_call": None,
            "needs_followup": False,
        }

    response_text = result["response"]
    api_call = result.get("api_call")
    needs_followup = result.get("needs_followup", False)

    # Persist conversation turn server-side
    await history.save_turn(
        db,
        employee_id=user.id,
        organization_id=user.organization_id,
        session_id=session_id,
        user_message=body.message,
        assistant_message=response_text,
    )

    # Audit every action regardless of success/failure
    elapsed_ms = int((time.monotonic() - start) * 1000)
    await audit.log_action(
        db,
        employee_id=user.id,
        organization_id=user.organization_id,
        intent_type=intent,
        action_taken=action_hint,
        api_called=api_call,
        result="success",
        llm_confidence=confidence,
        response_time_ms=elapsed_ms,
    )

    return ChatResponse(
        response=response_text,
        intent=intent,
        action=action_hint,
        api_call=api_call,
        session_id=session_id,
        needs_followup=needs_followup,
    )
