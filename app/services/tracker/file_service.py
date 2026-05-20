"""
File upload service — validates, stores, and registers attachments.
Supports: images, videos, documents, PDFs.
"""
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.attachment import TrackerAttachment
from app.models.tracker.task import TrackerTask
from sqlalchemy import select

UPLOAD_DIR = Path("uploads/tracker")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_ALLOWED: dict[str, str] = {
    # images
    "image/jpeg": "image", "image/png": "image", "image/gif": "image",
    "image/webp": "image",
    # videos
    "video/mp4": "video", "video/quicktime": "video", "video/webm": "video",
    # documents
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    # pdf
    "application/pdf": "pdf",
}


async def upload_attachment(
    db: AsyncSession,
    task_id: uuid.UUID,
    file: UploadFile,
    user: Employee,
) -> TrackerAttachment:
    # Verify task exists in org
    result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == task_id,
            TrackerTask.organization_id == user.organization_id,
        )
    )
    if not result.scalars().first():
        raise HTTPException(404, "Task not found")

    content_type = file.content_type or ""
    file_type = _ALLOWED.get(content_type)
    if not file_type:
        raise HTTPException(400, f"Unsupported file type: {content_type}")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File exceeds 50 MB limit")

    # Store under uploads/tracker/<task_id>/<uuid>_<filename>
    dest_dir = UPLOAD_DIR / str(task_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{Path(file.filename or 'file').name}"
    dest_path = dest_dir / safe_name
    dest_path.write_bytes(data)

    attachment = TrackerAttachment(
        task_id=task_id,
        file_url=str(dest_path).replace("\\", "/"),
        original_filename=file.filename or safe_name,
        file_type=file_type,
        file_size_bytes=len(data),
        uploaded_by=user.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def get_attachments(
    db: AsyncSession,
    task_id: uuid.UUID,
    org_id: uuid.UUID,
) -> list[TrackerAttachment]:
    result = await db.execute(
        select(TrackerTask).where(
            TrackerTask.id == task_id,
            TrackerTask.organization_id == org_id,
        )
    )
    if not result.scalars().first():
        raise HTTPException(404, "Task not found")

    result = await db.execute(
        select(TrackerAttachment)
        .where(TrackerAttachment.task_id == task_id)
        .order_by(TrackerAttachment.created_at.asc())
    )
    return result.scalars().all()
