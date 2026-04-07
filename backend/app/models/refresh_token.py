import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, Boolean, TIMESTAMP, text, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models import Base


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False
    )

    # NEW FIELD (IMPORTANT)
    token_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    token_hash: Mapped[str] = mapped_column(nullable=False)

    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False
    )

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