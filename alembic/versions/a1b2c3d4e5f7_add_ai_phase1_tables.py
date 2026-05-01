"""add ai phase1 tables

Revision ID: a1b2c3d4e5f7
Revises: d1e2f3a4b5c6
Create Date: 2026-04-28 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_conversation",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ai_conv_session", "ai_conversation", ["session_id"])
    op.create_index("idx_ai_conv_employee", "ai_conversation", ["employee_id"])

    op.create_table(
        "ai_audit_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("intent_type", sa.String(20), nullable=False),
        sa.Column("action_taken", sa.String(100), nullable=True),
        sa.Column("api_called", sa.String(100), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column("result", sa.String(20), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("llm_confidence", sa.Float(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ai_audit_employee", "ai_audit_log", ["employee_id"])
    op.create_index("idx_ai_audit_created", "ai_audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_ai_audit_created", table_name="ai_audit_log")
    op.drop_index("idx_ai_audit_employee", table_name="ai_audit_log")
    op.drop_table("ai_audit_log")
    op.drop_index("idx_ai_conv_session", table_name="ai_conversation")
    op.drop_index("idx_ai_conv_employee", table_name="ai_conversation")
    op.drop_table("ai_conversation")
