# app/models/employee.py
"""
Department and Employee models — partner's exact schema.

Table names are singular: 'department', 'employee'.
Employee uses google_id for OAuth linkage (our addition, nullable).
No password_hash — Google OAuth only.
"""

import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, ForeignKey, Boolean, Date, TIMESTAMP,
    CheckConstraint, text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Department(Base):
    __tablename__ = "department"

    __table_args__ = (
        UniqueConstraint("organization_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False
    )


class Employee(Base):
    """
    Single table for ALL users (employee + admin).
    role column controls permissions.
    google_id links to Google account — our addition for Google OAuth.
    """
    __tablename__ = "employee"

    __table_args__ = (
        CheckConstraint("role IN ('employee', 'admin')", name="check_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False
    )

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True
    )

    # From Google login
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # Google's unique user ID — our addition for OAuth linkage
    google_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )

    # Partner's column name (not avatar_url)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Partner's column name (not job_title)
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # RULE: 'employee' or 'admin' — enforced by CheckConstraint above
    role: Mapped[str] = mapped_column(
        String(20),
        server_default="employee",
        nullable=False
    )

    # Soft-delete: never hard-delete employees, their history stays
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False
    )

    joined_on: Mapped[date | None] = mapped_column(Date)

    last_login_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

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