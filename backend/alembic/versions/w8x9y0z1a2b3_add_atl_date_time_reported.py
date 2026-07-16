"""Add atl_date_time_reported to aircraft_technical_log

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-07-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "w8x9y0z1a2b3"
down_revision: Union[str, Sequence[str], None] = "v7w8x9y0z1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aircraft_technical_log",
        sa.Column("atl_date_time_reported", sa.DateTime(timezone=False), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("aircraft_technical_log", "atl_date_time_reported")
