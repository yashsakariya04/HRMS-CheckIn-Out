"""merge heads

Revision ID: f51336f6f6b2
Revises: 57517f078f2d, l1m2n3o4p5q6
Create Date: 2026-06-17 14:57:47.732270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f51336f6f6b2'
down_revision: Union[str, Sequence[str], None] = ('57517f078f2d', 'l1m2n3o4p5q6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
