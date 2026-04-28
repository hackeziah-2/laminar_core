"""Add auto_* time columns to aircraft_technical_log.

Revision ID: a4b5c6d7e8f9
Revises: c5d6e7f8a9b0
Create Date: 2026-04-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AUTO_FLOAT_COLS = (
    "auto_airframe_run_time",
    "auto_airframe_aftt",
    "auto_engine_run_time",
    "auto_run_time",
    "auto_engine_tsn",
    "auto_engine_tso",
    "auto_engine_tbo",
    "auto_propeller_run_time",
    "auto_propeller_tsn",
    "auto_propeller_tso",
    "auto_propeller_tbo",
)


def upgrade() -> None:
    for col in _AUTO_FLOAT_COLS:
        op.add_column(
            "aircraft_technical_log",
            sa.Column(col, sa.Float(), nullable=True),
        )


def downgrade() -> None:
    for col in reversed(_AUTO_FLOAT_COLS):
        op.drop_column("aircraft_technical_log", col)
