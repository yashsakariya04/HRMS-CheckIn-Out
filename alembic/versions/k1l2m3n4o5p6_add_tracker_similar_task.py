"""add tracker_similar_task table

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'k1l2m3n4o5p6'
down_revision = 'j1k2l3m4n5o6'
branch_labels = None
depends_on = None


def upgrade() -> None:
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
        sa.UniqueConstraint('source_task_id', 'target_task_id', name='uq_similar_task_pair'),
    )
    op.create_index('idx_similar_task_source', 'tracker_similar_task', ['source_task_id'])
    op.create_index('idx_similar_task_target', 'tracker_similar_task', ['target_task_id'])


def downgrade() -> None:
    op.drop_index('idx_similar_task_target', table_name='tracker_similar_task')
    op.drop_index('idx_similar_task_source', table_name='tracker_similar_task')
    op.drop_table('tracker_similar_task')
