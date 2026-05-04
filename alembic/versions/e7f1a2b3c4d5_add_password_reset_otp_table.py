"""add_password_reset_otp_table

Revision ID: e7f1a2b3c4d5
Revises: a1b2c3d4e5f6
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e7f1a2b3c4d5"
down_revision = "41ea5b326263"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_otp",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("otp_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_password_reset_otp_email", "password_reset_otp", ["email"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_otp_email", table_name="password_reset_otp")
    op.drop_table("password_reset_otp")
