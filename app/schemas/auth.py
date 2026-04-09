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
    """Body for POST /auth/login — email-only, no password."""
    email: EmailStr  # Validated as a proper email address format


class RefreshRequest(BaseModel):
    """Body for POST /auth/refresh and POST /auth/logout."""
    refresh_token: str  # The long-lived token received at login


class TokenResponse(BaseModel):
    """
    Returned after a successful login or token refresh.

    access_token  : Short-lived JWT (15 min). Send in every API request header.
    refresh_token : Long-lived opaque token (1 year). Use only to get new access tokens.
    token_type    : Always "bearer" — tells the client how to send the token.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class GoogleLoginRequest(BaseModel):
    """Body for POST /auth/google-login — Google OAuth flow."""
    id_token: str  # The ID token received from Google after the user signs in
