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
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.auth import GoogleLoginRequest, LoginRequest, RefreshRequest, TokenResponse
from app.services.auth_service import google_login, login, logout, refresh

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login_route(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Email-only login — no password required.
    Looks up the employee by email and issues tokens if they are active.
    Used for development/testing. Production uses google-login.
    """
    return await login(data.email, db)


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

    The frontend sends the ID token received from Google Sign-In.
    The backend verifies it with Google, looks up the employee by email,
    and returns access + refresh tokens if the employee exists and is active.
    """
    return await google_login(data.id_token, db)
