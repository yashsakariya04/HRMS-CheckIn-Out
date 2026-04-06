import uuid
from datetime import datetime, date
from sqlalchemy import String, ForeignKey, Boolean, Date, TIMESTAMP, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base


class Employee(Base):
    __tablename__ = "employee"

    #Auto-generated ID
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Comes from organizations table
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False
    )

    #  Comes from departments table (optional)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True
    )

    #  From Google login
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    #  You control this
    designation: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    #  Role system
    role: Mapped[str] = mapped_column(
        String(20),
        server_default="employee",
        nullable=False
    )

    #  Active / inactive user
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False
    )

    #  Optional join date
    joined_on: Mapped[date | None] = mapped_column(Date)

    #  Updated on login
    last_login_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    #  Auto timestamp (DB level)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False
    )

    #  Role constraint
    __table_args__ = (
        CheckConstraint("role IN ('employee', 'admin')", name="check_role"),
    )