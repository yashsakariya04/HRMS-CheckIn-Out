"""
app/ai/history.py — Server-Side Conversation History
======================================================
History is always loaded from DB by session_id.
The client only sends session_id (or nothing for a new session).
This prevents history injection attacks.
"""

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_conversation import AIConversation


async def load_history(db: AsyncSession, session_id: uuid.UUID, limit: int = 20) -> List[dict]:
    """
    Load the last `limit` turns for a session as a list of
    {"role": "user"|"assistant", "content": "..."} dicts
    ready to pass directly to the Groq messages array.
    """
    result = await db.execute(
        select(AIConversation)
        .where(AIConversation.session_id == session_id)
        .order_by(AIConversation.turn_number.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    # Return in chronological order
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


async def save_turn(
    db: AsyncSession,
    employee_id: uuid.UUID,
    organization_id: uuid.UUID,
    session_id: uuid.UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    """
    Persist one user+assistant turn to the database.
    Computes turn_number as max existing + 1.
    """
    result = await db.execute(
        select(AIConversation.turn_number)
        .where(AIConversation.session_id == session_id)
        .order_by(AIConversation.turn_number.desc())
        .limit(1)
    )
    last = result.scalar()
    next_turn = (last or 0) + 1

    db.add(AIConversation(
        employee_id=employee_id,
        organization_id=organization_id,
        session_id=session_id,
        role="user",
        content=user_message,
        turn_number=next_turn,
    ))
    db.add(AIConversation(
        employee_id=employee_id,
        organization_id=organization_id,
        session_id=session_id,
        role="assistant",
        content=assistant_message,
        turn_number=next_turn,
    ))
    await db.commit()
