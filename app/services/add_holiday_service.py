"""
app/services/add_holiday_service.py — Holiday Management Business Logic
=======================================================================
Handles creating, listing, and deleting company holidays.

Non-technical summary:
----------------------
Admins add official holidays to the company calendar. This service
enforces that:
  - Holidays cannot be added in the past.
  - No two holidays can fall on the same date for the same organization.
  - Holidays can be permanently deleted (hard delete, unlike employees/projects).
"""

from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models.holiday import Holiday
from app.models.organization import Organization


async def create_holiday(data, db) -> Holiday:
    """
    Add a new holiday to the company calendar.

    Args:
        data: SetHoliday with name, type (enum), and date.
        db:   Async database session.

    Returns:
        The newly created Holiday ORM object.

    Raises:
        400 — No organization found.
        400 — A holiday already exists on this date.
        400 — The date is in the past.
    """
    org_result = await db.execute(select(Organization))
    organization = org_result.scalars().first()
    if not organization:
        raise HTTPException(status_code=400, detail="No organization found")

    # Prevent duplicate holidays on the same date
    existing = await db.execute(
        select(Holiday).where(
            Holiday.organization_id == organization.id,
            Holiday.holiday_date == data.date,
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Holiday already exists for this date")

    # Prevent adding past holidays
    if data.date < date.today():
        raise HTTPException(status_code=400, detail="Cannot add past holiday")

    holiday = Holiday(
        name=data.name,
        holiday_date=data.date,
        holiday_type=data.type.value,  # Convert enum to string for storage
        organization_id=organization.id,
    )
    db.add(holiday)
    await db.commit()
    await db.refresh(holiday)
    return holiday


async def get_holidays(db) -> list:
    """
    Return all holidays for the organization.

    No filtering — returns past and future holidays.
    Used to display the full holiday calendar to employees.

    Args:
        db: Async database session.
    """
    result = await db.execute(select(Holiday))
    return result.scalars().all()


async def delete_holiday(holiday_id: UUID, db) -> dict:
    """
    Permanently delete a holiday (hard delete).

    Unlike employees and projects, holidays are hard-deleted since
    there are no dependent records that reference them.

    Args:
        holiday_id: UUID of the holiday to delete.
        db:         Async database session.

    Returns:
        Success message dict.

    Raises:
        404 — Holiday not found.
    """
    result = await db.execute(select(Holiday).where(Holiday.id == holiday_id))
    holiday = result.scalars().first()

    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")

    await db.delete(holiday)
    await db.commit()
    return {"message": "Holiday deleted successfully"}
