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
import random
import string

from fastapi import HTTPException
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_otp_email
from app.core.security import (
    create_access_token, create_refresh_token, create_reset_token,
    decode_reset_token, hash_password, hash_token, verify_password, verify_token,
)
from app.models.employee import Employee
from app.models.password_reset_otp import PasswordResetOTP
from app.models.refresh_token import RefreshToken


async def login(email: str, password: str, db: AsyncSession) -> dict:
    """
    Email + password login.

    Looks up the employee by email, verifies the password against the
    stored Argon2id hash, and issues tokens on success.
    """
    result = await db.execute(select(Employee).where(Employee.email == email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    if not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Set joined_on on first login if not already set
    if user.joined_on is None:
        user.joined_on = date.today()

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token({"sub": str(user.id), "role": user.role})
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
            and_(RefreshToken.token_id == token_id, RefreshToken.is_revoked == False)  # noqa: E712
        )
    )
    db_token = result.scalars().first()

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")
    if not verify_token(secret, db_token.token_hash):
        raise HTTPException(status_code=401, detail="Invalid token")

    access_token = create_access_token({"sub": str(db_token.employee_id)})
    return {"access_token": access_token, "refresh_token": refresh_token}


async def logout(refresh_token: str, db: AsyncSession, redis=None) -> None:
    try:
        token_id, _ = refresh_token.split(".")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token format")

    # Use UPDATE directly — no SELECT round-trip needed
    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_id == token_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
        .values(is_revoked=True)
        .returning(RefreshToken.employee_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid token")

    await db.commit()

    # Bust employee cache so a logged-out user can't ride the Redis cache
    if redis:
        await redis.delete(f"emp:{row.employee_id}")


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

    access_token = create_access_token({"sub": str(user.id), "role": user.role})
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
    


# ── OTP helper ────────────────────────────────────────────────────────────────

def _generate_otp() -> str:
    """Return a 6-digit numeric OTP string."""
    return "".join(random.choices(string.digits, k=6))


# ── Forgot password flow ──────────────────────────────────────────────────────

async def forgot_password(email: str, db: AsyncSession) -> None:
    """
    Step 1 — Request OTP.

    Always returns without error even if the email doesn't exist
    (prevents email enumeration). Sends OTP only when the employee exists.

    - Invalidates any previous unused OTP for this email.
    - Stores a new hashed OTP with a 10-minute expiry.
    - Sends the plain OTP via email.
    """
    # Check employee exists (but don't reveal the result to the caller)
    result = await db.execute(
        select(Employee.id).where(Employee.email == email, Employee.is_active == True)  # noqa: E712
    )
    employee_exists = result.first() is not None

    if employee_exists:
        # Invalidate all previous unused OTPs for this email
        prev_result = await db.execute(
            select(PasswordResetOTP).where(
                PasswordResetOTP.email == email,
                PasswordResetOTP.is_used == False,  # noqa: E712
            )
        )
        for old_row in prev_result.scalars().all():
            old_row.is_used = True

        # Generate and hash OTP
        otp = _generate_otp()
        from app.core.security import hash_password as hash_otp  # reuse argon2 hasher
        otp_hash = hash_otp(otp)

        db.add(PasswordResetOTP(
            email=email,
            otp_hash=otp_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        ))
        await db.commit()

        # Send email (fire — if this fails the OTP row is already committed)
        await send_otp_email(email, otp)


async def verify_otp(email: str, otp: str, db: AsyncSession) -> dict:
    """
    Step 2 — Verify OTP.

    Finds the latest unused, unexpired OTP row for the email.
    Enforces a 5-attempt brute-force limit.
    On success: marks OTP as used and returns a 15-min reset JWT.
    """
    result = await db.execute(
        select(PasswordResetOTP).where(
            PasswordResetOTP.email == email,
            PasswordResetOTP.is_used == False,  # noqa: E712
            PasswordResetOTP.expires_at > datetime.now(timezone.utc),
        ).order_by(PasswordResetOTP.created_at.desc())
    )
    otp_row = result.scalars().first()

    if not otp_row:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    if otp_row.attempts >= 5:
        raise HTTPException(status_code=400, detail="Too many attempts. Request a new OTP.")

    # Verify OTP against stored hash
    from app.core.security import verify_password as verify_otp_hash
    if not verify_otp_hash(otp, otp_row.otp_hash):
        otp_row.attempts += 1
        await db.commit()
        remaining = 5 - otp_row.attempts
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OTP. {remaining} attempt(s) remaining.",
        )

    # Mark as used — single use only
    otp_row.is_used = True
    await db.commit()

    reset_token = create_reset_token(email)
    return {"reset_token": reset_token}


async def reset_password(reset_token: str, new_password: str, confirm_password: str, db: AsyncSession) -> None:
    """
    Step 3 — Reset Password.

    Validates the reset JWT, checks passwords match, then updates the hash.
    """
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    email = decode_reset_token(reset_token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired reset token.")

    result = await db.execute(
        select(Employee).where(Employee.email == email, Employee.is_active == True)  # noqa: E712
    )
    employee = result.scalars().first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    employee.hashed_password = hash_password(new_password)
    await db.commit()
