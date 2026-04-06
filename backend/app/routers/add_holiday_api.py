from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.add_holiday import SetHoliday
from app.services.add_holiday_service import create_holiday,get_holidays
from app.dependencies.database import get_db
from app.dependencies.auth import require_admin

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