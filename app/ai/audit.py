"""
app/ai/audit.py — AI Audit Logger
===================================
Writes every AI action to the ai_audit_log table.
Called after every request regardless of success or failure.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_audit_log import AIAuditLog


async def log_action(
    db: AsyncSession,
    employee_id: uuid.UUID,
    organization_id: uuid.UUID,
    intent_type: str,
    action_taken: str | None = None,
    api_called: str | None = None,
    parameters: dict | None = None,
    result: str = "success",
    error_message: str | None = None,
    llm_confidence: float | None = None,
    response_time_ms: int | None = None,
) -> None:
    db.add(AIAuditLog(
        employee_id=employee_id,
        organization_id=organization_id,
        intent_type=intent_type,
        action_taken=action_taken,
        api_called=api_called,
        parameters=parameters,
        result=result,
        error_message=error_message,
        llm_confidence=llm_confidence,
        response_time_ms=response_time_ms,
    ))
    await db.commit()
