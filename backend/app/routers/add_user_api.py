# routers/employee.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.add_user import CreateEmployeeRequest, UpdateProfileRequest
from app.services.add_user_service import create_employee,update_profile
from app.dependencies.database import get_db
from app.dependencies.auth import require_admin, get_current_user

router = APIRouter(prefix="/employee", tags=["Employee"])

@router.post("/add")
async def add_employee(
    data: CreateEmployeeRequest,
    db: AsyncSession = Depends(get_db),
    admin = Depends(require_admin)
):
    return await create_employee(data, db)

@router.put("/update-profile")
async def update_profile_route(
    data: UpdateProfileRequest,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await update_profile(user, data, db)