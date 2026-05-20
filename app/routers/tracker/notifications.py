import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db, AsyncSessionLocal
from app.models.employee import Employee
from app.models.tracker.notification import TrackerNotification
from app.schemas.tracker.common import NotificationResponse
from app.services.tracker.ws_manager import ws_manager
from app.core.security import decode_token

router = APIRouter(prefix="/tracker/notifications", tags=["Tracker — Notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TrackerNotification)
        .where(TrackerNotification.user_id == user.id)
        .order_by(TrackerNotification.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(TrackerNotification)
        .where(
            TrackerNotification.id == notification_id,
            TrackerNotification.user_id == user.id,
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}


@router.patch("/read-all")
async def mark_all_read(
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(TrackerNotification)
        .where(
            TrackerNotification.user_id == user.id,
            TrackerNotification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: str):
    """
    WebSocket endpoint for real-time notifications.
    Connect with: ws://host/api/v1/tracker/notifications/ws?token=<access_token>
    """
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Employee).where(Employee.id == payload["sub"])
        )
        user = result.scalars().first()

    if not user or not user.is_active:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(user.id, websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user.id, websocket)
