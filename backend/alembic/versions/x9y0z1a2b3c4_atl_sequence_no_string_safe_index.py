"""Allow non-numeric ATL sequence_no strings (safe predecessor index).

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-07-17

The previous index cast every sequence_no to numeric, so inserts/updates with
alphanumeric values (e.g. QM-001) failed. Cast only when the value is numeric.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "x9y0z1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "w8x9y0z1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_atl_aircraft_batch_sequence_numeric")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_atl_aircraft_batch_sequence_numeric
        ON aircraft_technical_log (
            aircraft_fk,
            atl_batch_fk,
            ((CASE
                WHEN sequence_no ~ '^[0-9]+(\\.[0-9]+)?$' THEN sequence_no::numeric
                ELSE NULL
             END))
        )
        WHERE is_deleted IS FALSE
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_atl_aircraft_batch_sequence_numeric")
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
