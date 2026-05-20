import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.tracker.extension import ExtensionCreate, ExtensionAction, ExtensionResponse
from app.services.tracker import extension_service

router = APIRouter(prefix="/tracker/extensions", tags=["Tracker — Extensions"])


@router.post("", response_model=ExtensionResponse, status_code=201)
async def request_extension(
    payload: ExtensionCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.request_extension(db, payload, user)


@router.post("/{extension_id}/review", response_model=ExtensionResponse)
async def review_extension(
    extension_id: uuid.UUID,
    payload: ExtensionAction,
    admin: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.review_extension(db, extension_id, payload, admin)


@router.get("/pending", response_model=list[ExtensionResponse])
async def list_pending_extensions(
    admin: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.get_pending_extensions(db, admin.organization_id)
