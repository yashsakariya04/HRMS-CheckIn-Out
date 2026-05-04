"""
app/core/email.py — Email Sending via Gmail SMTP
"""

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

from app.core.config import settings


def _get_mailer() -> FastMail:
    """Build FastMail instance lazily so missing SMTP config only errors when actually sending."""
    conf = ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USER,
        MAIL_PASSWORD=settings.SMTP_PASSWORD,
        MAIL_FROM=settings.SMTP_FROM,
        MAIL_FROM_NAME=settings.SMTP_FROM_NAME,
        MAIL_PORT=settings.SMTP_PORT,
        MAIL_SERVER=settings.SMTP_HOST,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
    )
    return FastMail(conf)


async def send_otp_email(to_email: str, otp: str) -> None:
    """Send a password reset OTP email to the given address."""
    body = f"""
    <h3>Password Reset OTP</h3>
    <p>Your OTP for resetting your HRMS password is:</p>
    <h2 style="letter-spacing: 4px;">{otp}</h2>
    <p>This OTP is valid for <strong>10 minutes</strong> and can only be used once.</p>
    <p>If you did not request a password reset, ignore this email.</p>
    """
    message = MessageSchema(
        subject="HRMS — Password Reset OTP",
        recipients=[to_email],
        body=body,
        subtype=MessageType.html,
    )
    await _get_mailer().send_message(message)


# """
# app/core/email.py — Email Sending via Gmail API (OAuth2)
# """

# import base64
# from email.mime.text import MIMEText

# import httpx

# from app.core.config import settings

# TOKEN_URL = "https://oauth2.googleapis.com/token"
# GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


# async def _get_access_token() -> str:
#     async with httpx.AsyncClient() as client:
#         resp = await client.post(TOKEN_URL, data={
#             "client_id": settings.GOOGLE_CLIENT_ID,
#             "client_secret": settings.GOOGLE_CLIENT_SECRET,
#             "refresh_token": settings.GMAIL_REFRESH_TOKEN,
#             "grant_type": "refresh_token",
#         })
#         resp.raise_for_status()
#         return resp.json()["access_token"]


# async def send_otp_email(to_email: str, otp: str) -> None:
#     """Send a password reset OTP email via Gmail API."""
#     body = f"""
#     <h3>Password Reset OTP</h3>
#     <p>Your OTP for resetting your HRMS password is:</p>
#     <h2 style="letter-spacing: 4px;">{otp}</h2>
#     <p>This OTP is valid for <strong>10 minutes</strong> and can only be used once.</p>
#     <p>If you did not request a password reset, ignore this email.</p>
#     """
#     mime = MIMEText(body, "html")
#     mime["to"] = to_email
#     mime["from"] = f"{settings.GMAIL_FROM_NAME} <{settings.GMAIL_FROM}>"
#     mime["subject"] = "HRMS — Password Reset OTP"
#     raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

#     access_token = await _get_access_token()
#     async with httpx.AsyncClient() as client:
#         resp = await client.post(
#             GMAIL_SEND_URL,
#             headers={"Authorization": f"Bearer {access_token}"},
#             json={"raw": raw},
#         )
#         resp.raise_for_status()
