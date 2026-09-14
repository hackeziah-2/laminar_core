"""Add aircraft_id to atl_batch.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "atl_batch",
        sa.Column("aircraft_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_atl_batch_aircraft_id"),
        "atl_batch",
        ["aircraft_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_atl_batch_aircraft_id_aircrafts"),
        "atl_batch",
        "aircrafts",
        ["aircraft_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_atl_batch_aircraft_id_aircrafts"),
        "atl_batch",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_atl_batch_aircraft_id"), table_name="atl_batch")
    op.drop_column("atl_batch", "aircraft_id")
