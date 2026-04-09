"""
app/models/refresh_token.py — Refresh Token Database Model
===========================================================
Stores hashed refresh tokens used to issue new access tokens
without requiring the employee to log in again.

Non-technical summary:
----------------------
When an employee logs in, they get two tokens:
  1. Access token  — short-lived (15 min), used for every API call.
  2. Refresh token — long-lived (1 year), stored here in the database.

Only the SHA-256 hash of the refresh token is stored — never the raw value.
When the employee sends their refresh token to get a new access token,
we hash it and compare against the stored hash.

`is_revoked = True` means the token has been invalidated (logout).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class RefreshToken(Base):
    """ORM model for the `refresh_token` table."""
    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Which employee owns this token
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # The first half of the raw token (UUID before the dot) — used for lookup
    token_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    # SHA-256 hash of the second half (secret) — never store the raw secret
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # When this token expires (1 year from creation by default)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
    )

    # True after logout — revoked tokens cannot be used to get new access tokens
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
