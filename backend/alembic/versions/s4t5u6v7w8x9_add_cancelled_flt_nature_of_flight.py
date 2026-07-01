"""Add CANCELLED_FLT to nature_of_flight enum.

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op

revision: str = "s4t5u6v7w8x9"
down_revision: Union[str, Sequence[str], None] = "r3s4t5u6v7w8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE nature_of_flight ADD VALUE IF NOT EXISTS 'CANCELLED_FLT'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
