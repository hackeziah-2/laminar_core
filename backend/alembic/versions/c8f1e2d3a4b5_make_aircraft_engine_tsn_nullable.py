"""Make aircraft.engine_tsn nullable.

Revision ID: c8f1e2d3a4b5
Revises: 7dc267d99fde
Create Date: 2026-04-27 20:45:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8f1e2d3a4b5"
down_revision: Union[str, Sequence[str], None] = "7dc267d99fde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "aircrafts",
        "engine_tsn",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE aircrafts SET engine_tsn = 0 WHERE engine_tsn IS NULL")
    op.alter_column(
        "aircrafts",
        "engine_tsn",
        existing_type=sa.Float(),
        nullable=False,
    )
