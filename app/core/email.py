"""
app/core/email.py — Email Sending via Gmail API (OAuth2)
=========================================================
Uses Google OAuth2 refresh token to obtain a short-lived access token,
then sends email through the Gmail REST API.

No SMTP credentials or App Passwords required — only:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, GMAIL_FROM
"""

import base64
from email.mime.text import MIMEText

import httpx

from app.core.config import settings

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


async def _get_access_token() -> str:
    """Exchange the stored refresh token for a short-lived Gmail access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(_TOKEN_URL, data={
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "refresh_token": settings.GMAIL_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        })
        if resp.status_code != 200:
            raise RuntimeError(f"Gmail token exchange failed: {resp.status_code} — {resp.json()}")
        return resp.json()["access_token"]


async def send_otp_email(to_email: str, otp: str) -> None:
    """Send a password reset OTP email via the Gmail API."""
    body = f"""
    <h3>Password Reset OTP</h3>
    <p>Your OTP for resetting your HRMS password is:</p>
    <h2 style="letter-spacing: 4px;">{otp}</h2>
    <p>This OTP is valid for <strong>10 minutes</strong> and can only be used once.</p>
    <p>If you did not request a password reset, ignore this email.</p>
    """
    mime = MIMEText(body, "html")
    mime["to"] = to_email
    mime["from"] = f"{settings.GMAIL_FROM_NAME} <{settings.GMAIL_FROM}>"
    mime["subject"] = "HRMS — Password Reset OTP"
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

    access_token = await _get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _GMAIL_SEND_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
        )
        resp.raise_for_status()
