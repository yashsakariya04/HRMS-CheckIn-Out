"""replace similar_task with duplicate_group and merge_request tables; add task embedding

Revision ID: l1m2n3o4p5q6
Revises: k1l2m3n4o5p6
Create Date: 2025-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector
    _has_pgvector = True
except ImportError:
    _has_pgvector = False

revision = 'l1m2n3o4p5q6'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (safe — Supabase already has it)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Drop old tracker_similar_task table
    op.drop_table('tracker_similar_task')

    # Add task_vector column to tracker_task (GitLab team uses 768-dim Gemini embeddings)
    # Column may already exist from GitLab migration — use IF NOT EXISTS via raw SQL
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='tracker_task' AND column_name='task_vector'
            ) THEN
                ALTER TABLE tracker_task ADD COLUMN task_vector vector(768);
            END IF;
        END$$;
    """)

    # Create tracker_duplicate_group
    op.create_table(
        'tracker_duplicate_group',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('developer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('label', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), server_default='open', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('open','kept','merge_requested','merged','rejected')", name='chk_dup_group_status'),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['developer_id'], ['employee.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_dup_group_developer', 'tracker_duplicate_group', ['developer_id'])
    op.create_index('idx_dup_group_status', 'tracker_duplicate_group', ['status'])

    # Create tracker_duplicate_group_member
    op.create_table(
        'tracker_duplicate_group_member',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('role', sa.String(10), server_default='candidate', nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['tracker_duplicate_group.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tracker_task.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('group_id', 'task_id', name='uq_dup_group_member'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create tracker_merge_request
    op.create_table(
        'tracker_merge_request',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('requested_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('primary_task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['tracker_duplicate_group.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by'], ['employee.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['primary_task_id'], ['tracker_task.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['employee.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('group_id', name='uq_merge_request_group'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_merge_req_group', 'tracker_merge_request', ['group_id'])
    op.create_index('idx_merge_req_status', 'tracker_merge_request', ['status'])


def downgrade() -> None:
    op.drop_table('tracker_merge_request')
    op.drop_table('tracker_duplicate_group_member')
    op.drop_table('tracker_duplicate_group')
    op.execute("ALTER TABLE tracker_task DROP COLUMN IF EXISTS task_vector")
    op.create_table(
        'tracker_similar_task',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('source_task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relation_type', sa.String(20), server_default='similar', nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('linked_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_task_id'], ['tracker_task.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_task_id'], ['tracker_task.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_by'], ['employee.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
