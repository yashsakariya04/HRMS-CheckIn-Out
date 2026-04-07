# app/routers/holidays.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from typing import List
from datetime import date
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.employee import Employee
from app.models.holiday import Holiday
from app.schemas.attendance import HolidayResponse

router = APIRouter(prefix="/holidays", tags=["Holidays"])


class HolidayCreateRequest(BaseModel):
    name: str
    holiday_date: date
    holiday_type: Optional[str] = None


@router.get("", response_model=List[HolidayResponse])
def get_holidays(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Returns all holidays for the current year."""
    current_year = date.today().year
    holidays = db.query(Holiday).filter(
        Holiday.organization_id == current_user.organization_id,
        func.extract("year", Holiday.holiday_date) == current_year,
    ).order_by(Holiday.holiday_date).all()
    return holidays


@router.post("", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
def create_holiday(
    body: HolidayCreateRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """Admin adds a new holiday to the calendar."""
    holiday = Holiday(
        organization_id=current_user.organization_id,
        name=body.name,
        holiday_date=body.holiday_date,
        holiday_type=body.holiday_type,
    )
    db.add(holiday)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holiday already exists for this date.",
        )
    db.refresh(holiday)
    return holiday
