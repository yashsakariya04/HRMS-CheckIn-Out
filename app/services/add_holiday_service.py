from sqlalchemy import select
from fastapi import HTTPException
from datetime import date
from uuid import UUID

from app.models.holiday import Holiday
from app.models.organization import Organization


async def create_holiday(data, db):
    # 1. Get organization (same as your pattern)
    org_result = await db.execute(select(Organization))
    organization = org_result.scalars().first()

    if not organization:
        raise HTTPException(status_code=400, detail="No organization found")

    # 2. Check duplicate holiday (IMPORTANT)
    existing = await db.execute(
        select(Holiday).where(
            Holiday.organization_id == organization.id,
            Holiday.holiday_date == data.date
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Holiday already exists for this date")

    # 3. Optional validation (recommended)
    if data.date < date.today():
        raise HTTPException(status_code=400, detail="Cannot add past holiday")

    # 4. Create holiday
    holiday = Holiday(
        name=data.name,
        holiday_date=data.date,
        holiday_type=data.type.value,  # Enum → string
        organization_id=organization.id
    )

    db.add(holiday)
    await db.commit()
    await db.refresh(holiday)

    return holiday

async def get_holidays(db):
    result = await db.execute(select(Holiday))
    return result.scalars().all()


async def delete_holiday(holiday_id: UUID, db):
    result = await db.execute(select(Holiday).where(Holiday.id == holiday_id))
    holiday = result.scalars().first()

    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")

    await db.delete(holiday)
    await db.commit()

    return {"message": "Holiday deleted successfully"}