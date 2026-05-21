"""add leave_notification table

Revision ID: g8h2i3j4k5l6
Revises: f69c5e1f6256
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "g8h2i3j4k5l6"
down_revision = "f69c5e1f6256"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leave_notification",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", UUID(as_uuid=True), sa.ForeignKey("leave_wfh_request.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_leave_notif_user_unread", "leave_notification", ["user_id", "is_read"])


def downgrade() -> None:
    op.drop_index("idx_leave_notif_user_unread", table_name="leave_notification")
    op.drop_table("leave_notification")
