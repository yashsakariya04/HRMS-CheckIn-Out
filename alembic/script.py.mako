"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
<<<<<<< HEAD:alembic/script.py.mako
down_revision: Union[str, None] = ${repr(down_revision)}
=======
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
>>>>>>> 79d7bbbc70f75bf82e0cccd448c09823dd7299d6:backend/alembic/script.py.mako
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
<<<<<<< HEAD:alembic/script.py.mako
=======
    """Upgrade schema."""
>>>>>>> 79d7bbbc70f75bf82e0cccd448c09823dd7299d6:backend/alembic/script.py.mako
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
<<<<<<< HEAD:alembic/script.py.mako
=======
    """Downgrade schema."""
>>>>>>> 79d7bbbc70f75bf82e0cccd448c09823dd7299d6:backend/alembic/script.py.mako
    ${downgrades if downgrades else "pass"}
