"""add_checkout_time_to_leave_wfh_request

Revision ID: a1b2c3d4e5f6
Revises: c45ec8f8ef8e
Create Date: 2026-04-09 00:00:00.000000

Adds the checkout_time column to leave_wfh_request.
This column stores the exact checkout time submitted by the employee
for missing_time requests. NULL for all other request types.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c45ec8f8ef8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_wfh_request",
        sa.Column("checkout_time", sa.Time(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leave_wfh_request", "checkout_time")
