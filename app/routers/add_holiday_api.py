"""
app/routers/add_holiday_api.py — Holiday Management API Endpoints
=================================================================
Admin endpoints for managing the company holiday calendar.

Endpoints:
  POST   /api/v1/holiday/add      — Admin adds a new holiday
  GET    /api/v1/holiday/         — List all holidays (no auth required)
  DELETE /api/v1/holiday/{id}     — Admin removes a holiday
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.schemas.add_holiday import SetHoliday
from app.services.add_holiday_service import create_holiday, delete_holiday, get_holidays

router = APIRouter(prefix="/holiday", tags=["Holiday"])


@router.post("/add")
async def add_holiday(
    data: SetHoliday,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: add a new holiday to the company calendar.
    Returns 400 if a holiday already exists on that date, or if the date is in the past.
    """
    return await create_holiday(data, db)


@router.get("/")
async def list_holidays(
    db: AsyncSession = Depends(get_db),
):
    """
    Return all holidays. No authentication required.
    Used to display the holiday list to all employees.
    """
    return await get_holidays(db)


@router.delete("/{holiday_id}")
async def remove_holiday(
    holiday_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: permanently delete a holiday from the calendar.
    Returns 404 if the holiday is not found.
    """
    return await delete_holiday(holiday_id, db)
