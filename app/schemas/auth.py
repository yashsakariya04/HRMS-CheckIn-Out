"""
app/schemas/auth.py — Authentication Request/Response Schemas
=============================================================
Pydantic models that define the shape of data sent to and received
from the authentication endpoints.

Non-technical summary:
----------------------
These are the "forms" that the login/logout API endpoints accept and return.
Pydantic automatically validates that the data matches the expected format
before it reaches the business logic.

Schemas defined here:
  - LoginRequest      : Email-only login (no password — Google OAuth handles auth)
  - RefreshRequest    : Send a refresh token to get a new access token
  - TokenResponse     : What the server returns after a successful login/refresh
  - GoogleLoginRequest: Send a Google ID token to log in via Google OAuth
"""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Body for POST /auth/login — email + password."""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Body for POST /auth/refresh and POST /auth/logout."""
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class GoogleLoginRequest(BaseModel):
    """Body for POST /auth/google-login — Google OAuth flow."""
    id_token: str


class ForgotPasswordRequest(BaseModel):
    """Body for POST /auth/forgot-password."""
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    """Body for POST /auth/verify-otp."""
    email: EmailStr
    otp: str


class ResetPasswordRequest(BaseModel):
    """Body for POST /auth/reset-password."""
    reset_token: str
    new_password: str
    confirm_password: str
