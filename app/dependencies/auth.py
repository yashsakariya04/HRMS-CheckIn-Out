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
    """
    Verify the Bearer token and return the authenticated employee.

    Steps:
      1. Extract the raw token from the "Authorization: Bearer <token>" header.
      2. Decode and validate the JWT (checks signature and expiry).
      3. Look up the employee by the `sub` (subject) claim in the token.
      4. Return the Employee ORM object if everything checks out.

    Raises:
        401 — if the token is missing, invalid, or expired.
        404 — if the employee ID in the token no longer exists in the DB.
    """
    token = credentials.credentials  # Raw JWT string after "Bearer "

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    # `sub` contains the employee's UUID (set during login)
    result = await db.execute(
        select(Employee).where(Employee.id == payload["sub"])
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


async def require_admin(user: Employee = Depends(get_current_user)) -> Employee:
    """
    Extend get_current_user to also enforce admin-only access.

    Calls get_current_user first (full token validation), then checks
    that the employee's role is "admin".

    Raises:
        403 — if the authenticated user is not an admin.

    Returns:
        The admin Employee object (same as get_current_user).
    """
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
