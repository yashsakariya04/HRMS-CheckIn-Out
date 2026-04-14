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

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.dependencies.database import get_db
from app.models.employee import Employee

# Enables the "Authorize" button in Swagger UI (/docs) and extracts
# the Bearer token from the Authorization header automatically.
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Use role from token to skip DB lookup for admin-check in require_admin
    # Still fetch the full user object so routes have access to all fields
    result = await db.execute(
        select(Employee).where(Employee.id == payload["sub"])
    )
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


async def require_admin(user: Employee = Depends(get_current_user)) -> Employee:
    # Role is also in the JWT but we use the DB-fetched user for consistency
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
