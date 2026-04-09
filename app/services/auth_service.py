"""
app/services/auth_service.py — Authentication Business Logic
=============================================================
Handles all authentication operations: email login, Google OAuth login,
token refresh, and logout.

Non-technical summary:
----------------------
This is the "brain" behind the login system. When an employee tries to
log in, this service:
  1. Verifies their identity (email lookup or Google token verification)
  2. Checks they are an active employee in the system
  3. Creates and stores a refresh token in the database
  4. Returns access + refresh tokens to the frontend

The commented-out code at the top is the old synchronous version —
kept for reference. The active code below uses async/await for
better performance.
"""

# [Large block of old synchronous code omitted — see git history]

from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token, create_refresh_token, hash_token, verify_token,
)
from app.models.employee import Employee
from app.models.refresh_token import RefreshToken


async def login(email: str, db: AsyncSession) -> dict:
    """
    Email-only login — no password required.

    Looks up the employee by email, verifies they are active,
    updates their last_login_at timestamp, and issues tokens.

    Args:
        email: The employee's email address.
        db:    Async database session.

    Returns:
        Dict with access_token, refresh_token, and token_type.

    Raises:
        404 — Employee not found.
        403 — Employee account is inactive (deactivated by admin).
    """
    result = await db.execute(select(Employee).where(Employee.email == email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    # Set joined_on on first login if not already set
    if user.joined_on is None:
        user.joined_on = date.today()

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token()
    token_id, secret = refresh_token.split(".")

    db_token = RefreshToken(
        employee_id=user.id,
        token_id=token_id,
        token_hash=hash_token(secret),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_token)
    await db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


async def refresh(refresh_token: str, db: AsyncSession) -> dict:
    """
    Exchange a valid refresh token for a new access token.

    Splits the token into (token_id, secret), looks up the DB record,
    verifies the secret hash, and issues a new access token.

    Args:
        refresh_token: The raw refresh token string from the client.
        db:            Async database session.

    Returns:
        Dict with new access_token and the same refresh_token.

    Raises:
        400 — Invalid token format.
        401 — Token not found, revoked, expired, or hash mismatch.
    """
    try:
        token_id, secret = refresh_token.split(".")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token format")

    result = await db.execute(
        select(RefreshToken).where(
            and_(RefreshToken.token_id == token_id, RefreshToken.is_revoked == False)
        )
    )
    db_token = result.scalars().first()

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    if db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")
    if not verify_token(secret, db_token.token_hash):
        raise HTTPException(status_code=401, detail="Invalid token")

    access_token = create_access_token({"sub": str(db_token.employee_id)})
    return {"access_token": access_token, "refresh_token": refresh_token}


async def logout(refresh_token: str, db: AsyncSession) -> None:
    """
    Revoke a refresh token — effectively logs the employee out.

    Marks the token as is_revoked = True so it cannot be used again.

    Args:
        refresh_token: The raw refresh token string from the client.
        db:            Async database session.

    Raises:
        400 — Invalid token format.
        401 — Token not found or already revoked.
    """
    try:
        token_id, _ = refresh_token.split(".")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token format")

    result = await db.execute(
        select(RefreshToken).where(
            and_(RefreshToken.token_id == token_id, RefreshToken.is_revoked == False)
        )
    )
    db_token = result.scalars().first()

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_token.is_revoked = True
    await db.commit()


async def google_login(id_token_str: str, db: AsyncSession) -> dict:
    """
    Log in using a Google ID token (main production login flow).

    Verifies the token with Google's servers, extracts the user's email,
    name, and photo, then looks up the employee in the database.

    Auto-fills name and photo on first login if not already set.
    Issues HRMS access + refresh tokens on success.

    Args:
        id_token_str: The ID token received from Google Sign-In on the frontend.
        db:           Async database session.

    Returns:
        Dict with access_token, refresh_token, and token_type.

    Raises:
        401 — Google token is invalid or expired.
        403 — Email not registered in the system, or account is inactive.
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str, requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = idinfo.get("email")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    result = await db.execute(select(Employee).where(Employee.email == email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=403, detail="Access denied. Contact admin")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    # Auto-fill profile fields only if they are not already set
    if not user.full_name:
        user.full_name = name
    if not user.photo_url:
        user.photo_url = picture
    if user.joined_on is None:
        user.joined_on = date.today()

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token()
    token_id, secret = refresh_token.split(".")

    db_token = RefreshToken(
        employee_id=user.id,
        token_id=token_id,
        token_hash=hash_token(secret),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_token)
    await db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
