"""tracker_checklist_and_subtask_refactor

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-06-10 01:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "j1k2l3m4n5o6"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create tracker_checklist table
    op.create_table(
        "tracker_checklist",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tracker_task.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["employee.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tracker_checklist_task_id", "tracker_checklist", ["task_id"])

    # 2. Migrate existing subtasks — create one default checklist per task that had subtasks,
    #    then point subtasks to it
    op.execute("""
        INSERT INTO tracker_checklist (id, task_id, name, created_by)
        SELECT gen_random_uuid(), task_id, 'Checklist', created_by
        FROM (
            SELECT DISTINCT task_id, created_by FROM tracker_subtask
        ) sub;
    """)

    # 3. Add checklist_id column to tracker_subtask
    op.add_column("tracker_subtask", sa.Column("checklist_id", sa.UUID(), nullable=True))

    # 4. Populate checklist_id from the default checklists created above
    op.execute("""
        UPDATE tracker_subtask s
        SET checklist_id = c.id
        FROM tracker_checklist c
        WHERE c.task_id = s.task_id;
    """)

    # 5. Make checklist_id NOT NULL and add FK
    op.alter_column("tracker_subtask", "checklist_id", nullable=False)
    op.create_foreign_key(
        "fk_tracker_subtask_checklist_id", "tracker_subtask",
        "tracker_checklist", ["checklist_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("idx_tracker_subtask_checklist_id", "tracker_subtask", ["checklist_id"])

    # 6. Drop old task_id column from tracker_subtask
    op.drop_index("idx_tracker_subtask_task_id", table_name="tracker_subtask")
    op.drop_column("tracker_subtask", "task_id")


def downgrade() -> None:
    op.add_column("tracker_subtask", sa.Column("task_id", sa.UUID(), nullable=True))
    op.execute("""
        UPDATE tracker_subtask s
        SET task_id = c.task_id
        FROM tracker_checklist c
        WHERE c.id = s.checklist_id;
    """)
    op.alter_column("tracker_subtask", "task_id", nullable=False)
    op.create_foreign_key(
        "fk_tracker_subtask_task_id", "tracker_subtask",
        "tracker_task", ["task_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("idx_tracker_subtask_task_id", "tracker_subtask", ["task_id"])

    op.drop_index("idx_tracker_subtask_checklist_id", table_name="tracker_subtask")
    op.drop_constraint("fk_tracker_subtask_checklist_id", "tracker_subtask", type_="foreignkey")
    op.drop_column("tracker_subtask", "checklist_id")

    op.drop_index("idx_tracker_checklist_task_id", table_name="tracker_checklist")
    op.drop_table("tracker_checklist")
