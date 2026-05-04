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
