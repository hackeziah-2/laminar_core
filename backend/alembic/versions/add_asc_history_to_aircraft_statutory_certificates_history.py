"""add asc_history FK to aircraft_statutory_certificates_history

Revision ID: f8e9d0c1b2a3
Revises: e7f8a9b0c1d2
Create Date: 2026-03-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f8e9d0c1b2a3"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aircraft_statutory_certificates_history",
        sa.Column("asc_history", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_aircraft_statutory_certificates_history_asc_history",
        "aircraft_statutory_certificates_history",
        "aircraft_statutory_certificates",
        ["asc_history"],
        ["id"],
    )
    op.create_index(
        op.f("ix_aircraft_statutory_certificates_history_asc_history"),
        "aircraft_statutory_certificates_history",
        ["asc_history"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_aircraft_statutory_certificates_history_asc_history"),
        table_name="aircraft_statutory_certificates_history",
    )
    op.drop_constraint(
        "fk_aircraft_statutory_certificates_history_asc_history",
        "aircraft_statutory_certificates_history",
        type_="foreignkey",
    )
    op.drop_column("aircraft_statutory_certificates_history", "asc_history")
