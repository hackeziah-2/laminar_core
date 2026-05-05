"""Make aircraft.propeller_tsn nullable.

Revision ID: d1e2f3a4b5c6
Revises: c8f1e2d3a4b5
Create Date: 2026-04-27 21:48:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c8f1e2d3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "aircrafts",
        "propeller_tsn",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE aircrafts SET propeller_tsn = 0 WHERE propeller_tsn IS NULL")
    op.alter_column(
        "aircrafts",
        "propeller_tsn",
        existing_type=sa.Float(),
        nullable=False,
    )
