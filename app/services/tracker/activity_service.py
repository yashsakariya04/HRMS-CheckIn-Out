"""
Activity log service — append-only timeline writer.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracker.activity_log import TrackerActivityLog


async def log_activity(
    db: AsyncSession,
    task_id: uuid.UUID,
    action: str,
    detail: str,
    performed_by: uuid.UUID | None = None,
) -> None:
    entry = TrackerActivityLog(
        task_id=task_id,
        action=action,
        detail=detail,
        performed_by=performed_by,
    )
    db.add(entry)
    await db.flush()
