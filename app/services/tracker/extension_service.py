"""
Deadline extension request service.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.extension_request import TrackerExtensionRequest
from app.models.tracker.task import TrackerTask, TrackerTaskMember
from app.schemas.tracker.extension import ExtensionCreate, ExtensionAction
from app.services.tracker.activity_service import log_activity
from app.services.tracker.notification_service import notify
from app.services.tracker.task_service import _get_org_admins


async def request_extension(
    db: AsyncSession,
    payload: ExtensionCreate,
    user: Employee,
) -> TrackerExtensionRequest:
    result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == payload.task_id,
            TrackerTask.organization_id == user.organization_id,
        )
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(404, "Task not found")

    member_ids = {m.employee_id for m in task.members}
    if user.role == "employee" and user.id not in member_ids and task.created_by != user.id:
        raise HTTPException(403, "Task not assigned to you")

    # Only one pending extension per task at a time
    existing = await db.execute(
        select(TrackerExtensionRequest).where(
            TrackerExtensionRequest.task_id == payload.task_id,
            TrackerExtensionRequest.status == "pending",
        )
    )
    if existing.scalars().first():
        raise HTTPException(400, "A pending extension request already exists for this task")

    if task.deadline and payload.new_deadline <= task.deadline:
        raise HTTPException(400, "Proposed deadline must be later than the current deadline")

    ext = TrackerExtensionRequest(
        task_id=payload.task_id,
        requested_by=user.id,
        new_deadline=payload.new_deadline,
        reason=payload.reason,
        comment=payload.comment,
    )
    db.add(ext)
    await db.flush()

    await log_activity(
        db, payload.task_id, "extension_requested",
        f"Deadline extension requested to {payload.new_deadline.strftime('%Y-%m-%d')}: {payload.reason}",
        user.id,
    )

    admins = await _get_org_admins(db, user.organization_id)
    for admin in admins:
        await notify(
            db, admin.id,
            "Deadline Extension Requested",
            f"{user.full_name or user.email} requested deadline extension to {payload.new_deadline.strftime('%Y-%m-%d')} on '{task.title}'",
            payload.task_id,
        )

    await db.commit()
    await db.refresh(ext)
    return ext


async def review_extension(
    db: AsyncSession,
    extension_id: uuid.UUID,
    payload: ExtensionAction,
    admin: Employee,
) -> TrackerExtensionRequest:
    if payload.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be 'approve' or 'reject'")

    result = await db.execute(
        select(TrackerExtensionRequest).where(TrackerExtensionRequest.id == extension_id)
    )
    ext = result.scalars().first()
    if not ext:
        raise HTTPException(404, "Extension request not found")
    if ext.status != "pending":
        raise HTTPException(400, "Extension request already reviewed")

    # Verify task belongs to admin's org
    result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == ext.task_id,
            TrackerTask.organization_id == admin.organization_id,
        )
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(403, "Task does not belong to your organization")

    ext.status = "approved" if payload.action == "approve" else "rejected"
    ext.reviewed_by = admin.id
    ext.admin_note = payload.admin_note
    ext.reviewed_at = datetime.now(timezone.utc)

    if payload.action == "approve":
        task.deadline = ext.new_deadline
        task.updated_at = datetime.now(timezone.utc)

    action_label = "extension_approved" if payload.action == "approve" else "extension_rejected"
    detail = (
        f"Deadline extension {ext.status} by {admin.full_name or admin.email}"
        + (f" — {payload.admin_note}" if payload.admin_note else "")
    )
    await log_activity(db, ext.task_id, action_label, detail, admin.id)

    await notify(
        db, ext.requested_by,
        f"Extension {ext.status.capitalize()}",
        f"Your deadline extension for '{task.title}' was {ext.status}",
        ext.task_id,
    )

    await db.commit()
    await db.refresh(ext)
    return ext


async def get_pending_extensions(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[TrackerExtensionRequest]:
    result = await db.execute(
        select(TrackerExtensionRequest)
        .join(TrackerTask, TrackerTask.id == TrackerExtensionRequest.task_id)
        .where(
            TrackerTask.organization_id == org_id,
            TrackerExtensionRequest.status == "pending",
        )
        .order_by(TrackerExtensionRequest.created_at.asc())
    )
    return result.scalars().all()
