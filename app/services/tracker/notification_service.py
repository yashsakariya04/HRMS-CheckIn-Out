"""
Notification service — creates DB records and pushes real-time WS events.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracker.notification import TrackerNotification
from app.services.tracker.ws_manager import ws_manager


async def notify(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    message: str,
    task_id: uuid.UUID | None = None,
) -> None:
    notif = TrackerNotification(
        user_id=user_id,
        task_id=task_id,
        title=title,
        message=message,
    )
    db.add(notif)
    await db.flush()  # get the id without committing

    await ws_manager.send_to_user(
        user_id,
        {
            "type": "notification",
            "id": str(notif.id),
            "title": title,
            "message": message,
            "task_id": str(task_id) if task_id else None,
        },
    )
