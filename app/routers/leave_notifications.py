import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.models.leave_notification import LeaveNotification

router = APIRouter(prefix="/leave-notifications", tags=["Leave Notifications"])


@router.get("")
async def list_leave_notifications(
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LeaveNotification)
        .where(LeaveNotification.user_id == user.id)
        .order_by(LeaveNotification.created_at.desc())
        .limit(50)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(n.id),
            "request_id": str(n.request_id) if n.request_id else None,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in rows
    ]


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(LeaveNotification)
        .where(
            LeaveNotification.id == notification_id,
            LeaveNotification.user_id == user.id,
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
        update(LeaveNotification)
        .where(
            LeaveNotification.user_id == user.id,
            LeaveNotification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}
