"""
app/routers/superadmin.py — Superadmin API Endpoints
=====================================================
Endpoints exclusively for the superadmin role.

Endpoints:
  GET   /api/v1/superadmin/users              — List all employees and admins
  PATCH /api/v1/superadmin/users/{id}/promote — Promote employee to admin
  PATCH /api/v1/superadmin/users/{id}/demote  — Demote admin to employee
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import require_superadmin
from app.dependencies.database import get_db
from app.dependencies.redis import get_redis
from app.schemas.add_user import EmployeeListItem
from app.services.superadmin_service import demote_to_employee, list_all_users, promote_to_admin

router = APIRouter(prefix="/superadmin", tags=["Superadmin"])


@router.get("/users", response_model=list[EmployeeListItem])
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin),
):
    """Superadmin only: list every user regardless of role."""
    return await list_all_users(db)


@router.patch("/users/{employee_id}/promote")
async def promote_employee(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin),
    redis=Depends(get_redis),
):
    """Superadmin only: grant admin role to an employee."""
    return await promote_to_admin(employee_id, db, redis)


@router.patch("/users/{employee_id}/demote")
async def demote_employee(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin),
    redis=Depends(get_redis),
):
    """Superadmin only: revoke admin role, revert to employee."""
    return await demote_to_employee(employee_id, db, redis)
