"""add white_atl_web_link and dfp_web_link to aircraft_technical_log

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-06-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h3i4j5k6l7m8"
down_revision: Union[str, Sequence[str], None] = "g2h3i4j5k6l7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aircraft_technical_log",
        sa.Column("white_atl_web_link", sa.Text(), nullable=True),
    )
    op.add_column(
        "aircraft_technical_log",
        sa.Column("dfp_web_link", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("aircraft_technical_log", "dfp_web_link")
    op.drop_column("aircraft_technical_log", "white_atl_web_link")
