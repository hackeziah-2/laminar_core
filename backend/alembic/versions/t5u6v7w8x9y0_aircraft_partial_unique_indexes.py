"""Replace aircraft registration/msn unique indexes with partial active-only indexes.

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op

revision: str = "t5u6v7w8x9y0"
down_revision: Union[str, Sequence[str], None] = "s4t5u6v7w8x9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_aircrafts_registration", table_name="aircrafts")
    op.drop_index("ix_aircrafts_msn", table_name="aircrafts")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_aircrafts_registration_active
        ON aircrafts (registration)
        WHERE is_deleted IS FALSE
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_aircrafts_msn_active
        ON aircrafts (msn)
        WHERE is_deleted IS FALSE
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_aircrafts_registration_active")
    op.execute("DROP INDEX IF EXISTS uq_aircrafts_msn_active")
    op.create_index("ix_aircrafts_registration", "aircrafts", ["registration"], unique=True)
    op.create_index("ix_aircrafts_msn", "aircrafts", ["msn"], unique=True)
