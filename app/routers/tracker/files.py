import uuid

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.tracker.attachment import AttachmentResponse
from app.services.tracker import file_service

router = APIRouter(prefix="/tracker/tasks/{task_id}/attachments", tags=["Tracker — Files"])


@router.post("", response_model=AttachmentResponse, status_code=201)
async def upload_file(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await file_service.upload_attachment(db, task_id, file, user)


@router.get("", response_model=list[AttachmentResponse])
async def list_attachments(
    task_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await file_service.get_attachments(db, task_id, user.organization_id)


@router.get("/download/{attachment_id}")
async def download_file(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.tracker.attachment import TrackerAttachment
    from fastapi import HTTPException

    result = await db.execute(
        select(TrackerAttachment).where(
            TrackerAttachment.id == attachment_id,
            TrackerAttachment.task_id == task_id,
        )
    )
    att = result.scalars().first()
    if not att:
        raise HTTPException(404, "Attachment not found")

    return FileResponse(
        path=att.file_url,
        filename=att.original_filename,
        media_type="application/octet-stream",
    )
