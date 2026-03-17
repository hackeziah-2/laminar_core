"""Add TSN and TSO for engine and propeller to aircrafts

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-03-17

Adds propeller_tsn, propeller_tso, engine_tsn, engine_tso (FLOAT DEFAULT 0)
for aviation maintenance tracking (Time Since New / Time Since Overhaul).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aircrafts",
        sa.Column("propeller_tsn", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "aircrafts",
        sa.Column("propeller_tso", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "aircrafts",
        sa.Column("engine_tsn", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "aircrafts",
        sa.Column("engine_tso", sa.Float(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("aircrafts", "engine_tso")
    op.drop_column("aircrafts", "engine_tsn")
    op.drop_column("aircrafts", "propeller_tso")
    op.drop_column("aircrafts", "propeller_tsn")
