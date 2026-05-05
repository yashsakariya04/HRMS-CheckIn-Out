"""
app/routers/auth.py — Authentication API Endpoints
===================================================
Handles all login, logout, and token management routes.

Endpoints:
  POST /api/v1/auth/login         — Email-only login (returns tokens)
  POST /api/v1/auth/refresh       — Exchange refresh token for new access token
  POST /api/v1/auth/logout        — Revoke refresh token (log out)
  GET  /api/v1/auth/me            — Get the currently logged-in employee's profile
  POST /api/v1/auth/google-login  — Log in using a Google ID token (main login flow)
"""

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.core.config import settings
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.auth import (
    ForgotPasswordRequest, GoogleLoginRequest, LoginRequest,
    RefreshRequest, ResetPasswordRequest, TokenResponse, VerifyOTPRequest,
)
from app.services.auth_service import (
    forgot_password, google_login, login, logout, refresh,
    reset_password, verify_otp,
)

_GMAIL_SCOPES = "https://www.googleapis.com/auth/gmail.send"
_GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login_route(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Email + password login. Returns access and refresh tokens.
    """
    return await login(data.email, data.password, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_route(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access token.
    Called automatically by the frontend when the access token expires.
    """
    return await refresh(data.refresh_token, db)


@router.post("/logout")
async def logout_route(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Revoke the refresh token — effectively logs the employee out.
    After this, the refresh token cannot be used to get new access tokens.
    """
    await logout(data.refresh_token, db)
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    """
    Return the profile of the currently authenticated employee.
    Requires a valid access token in the Authorization header.
    """
    return user


@router.post("/google-login", response_model=TokenResponse)
async def google_login_route(data: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Main login flow — verify a Google ID token and issue HRMS tokens.
    """
    return await google_login(data.id_token, db)


@router.post("/forgot-password", status_code=200)
async def forgot_password_route(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1 — Request a password reset OTP.
    Always returns 200 regardless of whether the email exists (prevents enumeration).
    """
    await forgot_password(data.email, db)
    return {"message": "If that email is registered, an OTP has been sent."}


@router.post("/verify-otp")
async def verify_otp_route(
    data: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2 — Verify the OTP.
    Returns a short-lived reset_token JWT on success.
    """
    return await verify_otp(data.email, data.otp, db)


@router.post("/reset-password", status_code=200)
async def reset_password_route(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 3 — Set a new password using the reset_token from Step 2.
    """
    await reset_password(data.reset_token, data.new_password, data.confirm_password, db)
    return {"message": "Password reset successful. You can now log in."}


# ── Gmail OAuth2 one-time setup endpoints ─────────────────────────────────────
# Use these ONCE to get the GMAIL_REFRESH_TOKEN for your .env file.
# Step 1: Open GET /auth/gmail/authorize in your browser
# Step 2: Google redirects to /auth/gmail/callback — refresh token is printed in terminal

@router.get("/gmail/authorize", include_in_schema=False)
async def gmail_authorize():
    """Redirect to Google consent screen to authorize Gmail sending."""
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": settings.GMAIL_CLIENT_ID,
        "redirect_uri": settings.GMAIL_REDIRECT_URI,
        "response_type": "code",
        "scope": _GMAIL_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })
    return RedirectResponse(_GMAIL_AUTH_URL + "?" + params)


@router.get("/gmail/callback", include_in_schema=False)
async def gmail_callback(code: str):
    """Exchange the authorization code for tokens and print the refresh token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(_GMAIL_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "redirect_uri": settings.GMAIL_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        data = resp.json()

    refresh_token = data.get("refresh_token", "")
    if not refresh_token:
        return {"error": "No refresh token returned. Make sure prompt=consent and access_type=offline are set.", "response": data}

    print("\n" + "=" * 60)
    print("Add this to your .env file:")
    print(f"GMAIL_REFRESH_TOKEN={refresh_token}")
    print("=" * 60 + "\n")

    return {
        "message": "Success! Copy the GMAIL_REFRESH_TOKEN from your server terminal into .env. You can now remove these setup endpoints.",
        "refresh_token": refresh_token,
    }
