# app/models/refresh_token.py
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Boolean, TIMESTAMP, text, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Unique identifier used for token rotation detection
    token_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    # SHA-256 hash of the raw token — raw token is NEVER stored
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False
    )

    # RULE: On logout, set is_revoked=True. Never delete. Purge job cleans nightly.
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False
    )