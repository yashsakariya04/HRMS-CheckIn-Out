"""
Leave notification service — DB record + real-time WS push for leave events.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave_notification import LeaveNotification
from app.services.tracker.ws_manager import ws_manager


async def notify_leave(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    message: str,
    request_id: uuid.UUID | None = None,
) -> None:
    notif = LeaveNotification(
        user_id=user_id,
        request_id=request_id,
        title=title,
        message=message,
    )
    db.add(notif)
    await db.flush()

    await ws_manager.send_to_user(
        user_id,
        {
            "type": "leave_notification",
            "id": str(notif.id),
            "title": title,
            "message": message,
            "request_id": str(request_id) if request_id else None,
        },
    )
