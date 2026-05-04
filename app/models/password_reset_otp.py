"""
app/models/password_reset_otp.py — Password Reset OTP Table
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otp"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
