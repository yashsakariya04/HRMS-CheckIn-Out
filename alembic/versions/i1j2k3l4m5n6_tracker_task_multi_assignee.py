"""tracker_task_multi_assignee

Revision ID: i1j2k3l4m5n6
Revises: h1i2j3k4l5m6
Create Date: 2026-06-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "i1j2k3l4m5n6"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create tracker_task_member association table
    op.create_table(
        "tracker_task_member",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("added_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tracker_task.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "employee_id"),
    )
    op.create_index("idx_tracker_task_member_task_id", "tracker_task_member", ["task_id"])
    op.create_index("idx_tracker_task_member_employee_id", "tracker_task_member", ["employee_id"])

    # 2. Migrate existing assigned_to rows into the new table
    op.execute("""
        INSERT INTO tracker_task_member (task_id, employee_id)
        SELECT id, assigned_to
        FROM tracker_task
        WHERE assigned_to IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)

    # 3. Drop old assigned_to column and its index
    op.drop_index("idx_tracker_task_assigned_to", table_name="tracker_task")
    op.drop_column("tracker_task", "assigned_to")


def downgrade() -> None:
    # Re-add assigned_to column (picks first member as the single assignee)
    op.add_column("tracker_task", sa.Column("assigned_to", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "tracker_task_assigned_to_fkey", "tracker_task",
        "employee", ["assigned_to"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_tracker_task_assigned_to", "tracker_task", ["assigned_to"])

    op.execute("""
        UPDATE tracker_task t
        SET assigned_to = (
            SELECT employee_id FROM tracker_task_member
            WHERE task_id = t.id
            LIMIT 1
        );
    """)

    op.drop_index("idx_tracker_task_member_employee_id", table_name="tracker_task_member")
    op.drop_index("idx_tracker_task_member_task_id", table_name="tracker_task_member")
    op.drop_table("tracker_task_member")
