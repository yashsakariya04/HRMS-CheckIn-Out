"""
app/routers/add_user_api.py — Employee Management API Endpoints
===============================================================
Admin endpoints for adding, updating, and deactivating employees.

Endpoints:
  GET    /api/v1/employee/         — Admin lists all employees
  POST   /api/v1/employee/add              — Admin adds a new employee
  PUT    /api/v1/employee/update-profile   — Employee updates their own profile
  DELETE /api/v1/employee/{employee_id}    — Admin deactivates an employee (soft delete)
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.schemas.add_user import CreateEmployeeRequest, EmployeeListItem, UpdateProfileRequest
from app.services.add_user_service import create_employee, delete_employee, list_employees, update_profile

router = APIRouter(prefix="/employee", tags=["Employee"])


@router.get("/", response_model=list[EmployeeListItem])
async def get_all_employees(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: list all employees with email, designation, and department name.
    Matches the Employees table in the UI. Sorted alphabetically by email.
    """
    return await list_employees(db)


@router.post("/add")
async def add_employee(
    data: CreateEmployeeRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: register a new employee in the system.

    The employee is created with their email, department, and designation.
    They can log in via Google once their email is registered here.
    Returns 400 if an employee with the same email already exists.
    """
    return await create_employee(data, db)


@router.put("/update-profile")
async def update_profile_route(
    data: UpdateProfileRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Any authenticated employee can update their own display name and photo URL.
    Other fields (email, role, department) require admin action.
    """
    return await update_profile(user, data, db)


@router.delete("/{employee_id}")
async def remove_employee(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: deactivate an employee (soft delete — sets is_active = False).

    The employee's data is preserved. They can no longer log in.
    Returns 404 if not found, 400 if already deactivated.
    """
    return await delete_employee(employee_id, db)
