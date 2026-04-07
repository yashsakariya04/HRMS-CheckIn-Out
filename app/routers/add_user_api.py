# routers/add_user_api.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.employee import Employee
from app.schemas.add_user import CreateEmployeeRequest, UpdateProfileRequest
from app.services.add_user_service import create_employee, update_profile

router = APIRouter(prefix="/employee", tags=["Employee"])


@router.post("/add")
def add_employee(
    data: CreateEmployeeRequest,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
):
    return create_employee(data, db)


@router.put("/update-profile")
def update_profile_route(
    data: UpdateProfileRequest,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_profile(user, data, db)
