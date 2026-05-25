"""
app/dependencies/auth.py — Authentication & Authorization Dependencies
======================================================================
Provides FastAPI dependencies that protect routes by verifying the
caller's identity and role.

Non-technical summary:
----------------------
Think of these as "security guards" placed at the door of each API endpoint.

  - `get_current_user` : Checks the Bearer token in the request header,
                         decodes it, and returns the logged-in employee.
                         Any authenticated employee (admin or regular) passes.

  - `require_admin`    : Calls get_current_user first, then additionally
                         checks that the employee's role is "admin".
                         Regular employees are blocked with a 403 error.

How to use in a router:
    # Any logged-in employee:
    async def my_route(user = Depends(get_current_user)): ...

    # Admin only:
    async def admin_route(admin = Depends(require_admin)): ...
"""
import json
import uuid
from datetime import date

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.dependencies.database import get_db
from app.dependencies.redis import get_redis
from app.models.employee import Employee

# Enables the "Authorize" button in Swagger UI (/docs) and extracts
# the Bearer token from the Authorization header automatically.
security = HTTPBearer()

_EMPLOYEE_CACHE_TTL = 300  # 5 minutes


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Employee:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    employee_id = payload["sub"]
    cache_key = f"emp:{employee_id}"

    cached = await redis.get(cache_key)
    if cached:
        data = json.loads(cached)
        data["id"] = uuid.UUID(data["id"])
        data["organization_id"] = uuid.UUID(data["organization_id"])
        if data.get("department_id"):
            data["department_id"] = uuid.UUID(data["department_id"])
        if data.get("joined_on"):
            data["joined_on"] = date.fromisoformat(data["joined_on"])
        user = Employee(**data)
        return user

    result = await db.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Cache all fields that services access downstream
    await redis.set(
        cache_key,
        json.dumps({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organization_id": str(user.organization_id),
            "is_active": user.is_active,
            "designation": user.designation,
            "photo_url": user.photo_url,
            "joined_on": user.joined_on.isoformat() if user.joined_on else None,
            "department_id": str(user.department_id) if user.department_id else None,
        }),
        ex=_EMPLOYEE_CACHE_TTL,
    )
    return user


async def require_admin(user: Employee = Depends(get_current_user)) -> Employee:
    # superadmin also passes admin-level checks
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_superadmin(user: Employee = Depends(get_current_user)) -> Employee:
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user
