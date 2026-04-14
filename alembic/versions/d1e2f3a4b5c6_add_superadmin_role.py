"""add_superadmin_role

Revision ID: d1e2f3a4b5c6
Revises: a1b2c3d4e5f6
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('check_role', 'employee', type_='check')
    op.create_check_constraint(
        'check_role',
        'employee',
        "role IN ('employee', 'admin', 'superadmin')",
    )


def downgrade() -> None:
    op.drop_constraint('check_role', 'employee', type_='check')
    op.create_check_constraint(
        'check_role',
        'employee',
        "role IN ('employee', 'admin')",
    )
