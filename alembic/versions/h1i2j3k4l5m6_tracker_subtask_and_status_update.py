"""tracker_subtask_and_status_update

Revision ID: h1i2j3k4l5m6
Revises: g8h2i3j4k5l6
Create Date: 2026-06-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "h1i2j3k4l5m6"
down_revision = "g8h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop old status check constraint
    op.drop_constraint("chk_tracker_task_status", "tracker_task", type_="check")

    # 2. Migrate any rows using removed statuses to nearest equivalent
    op.execute("""
        UPDATE tracker_task SET status = 'in_progress'  WHERE status = 'blocked';
        UPDATE tracker_task SET status = 'in_qa'        WHERE status = 'testing';
        UPDATE tracker_task SET status = 'in_production' WHERE status = 'completed';
    """)

    # 3. Add new status check constraint with 9 statuses
    op.create_check_constraint(
        "chk_tracker_task_status",
        "tracker_task",
        "status IN ('pending_approval','assigned','todo','in_progress',"
        "'in_development','in_qa','in_stage','in_production','rejected')",
    )

    # 4. Create tracker_subtask table
    op.create_table(
        "tracker_subtask",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("is_done", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tracker_task.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["employee.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tracker_subtask_task_id", "tracker_subtask", ["task_id"])


def downgrade() -> None:
    op.drop_index("idx_tracker_subtask_task_id", table_name="tracker_subtask")
    op.drop_table("tracker_subtask")

    op.drop_constraint("chk_tracker_task_status", "tracker_task", type_="check")
    op.create_check_constraint(
        "chk_tracker_task_status",
        "tracker_task",
        "status IN ('pending_approval','assigned','todo','in_progress',"
        "'blocked','testing','completed','rejected')",
    )
