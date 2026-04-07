from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from backend.app.schemas.add_holiday import SetHoliday
from backend.app.services.add_holiday_service import create_holiday, get_holidays, delete_holiday
from backend.app.dependencies.database import get_db
from backend.app.dependencies.auth import require_admin

router = APIRouter(prefix="/holiday", tags=["Holiday"])


@router.post("/add")
async def add_holiday(
    data: SetHoliday,
    db: AsyncSession = Depends(get_db),
    admin = Depends(require_admin)
):
    return await create_holiday(data, db)

@router.get("/")
async def list_holidays(
    db: AsyncSession = Depends(get_db)
):
    return await get_holidays(db)


@router.delete("/{holiday_id}")
async def remove_holiday(
    holiday_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin = Depends(require_admin)
):
    return await delete_holiday(holiday_id, db)