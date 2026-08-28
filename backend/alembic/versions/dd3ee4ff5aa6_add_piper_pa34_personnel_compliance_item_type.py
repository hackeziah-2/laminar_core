"""Add PIPER PA-34 to personnel_compliance_item_type enum.

Revision ID: dd3ee4ff5aa6
Revises: cc2dd3ee4ff5
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "dd3ee4ff5aa6"
down_revision: Union[str, Sequence[str], None] = "cc2dd3ee4ff5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE personnel_compliance_item_type ADD VALUE IF NOT EXISTS 'PIPER PA-34'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
