"""Add index for ATL predecessor lookups by aircraft, batch, and numeric sequence.

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_atl_aircraft_batch_sequence_numeric
        ON aircraft_technical_log (
            aircraft_fk,
            atl_batch_fk,
            ((sequence_no)::numeric)
        )
        WHERE is_deleted IS FALSE
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_atl_aircraft_batch_sequence_numeric")
