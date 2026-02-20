"""update aircraft fields: remove type/airframe_model/airframe_serial_number; add life time limits

Revision ID: update_aircraft_life_limits
Revises: add_email_last_login
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "update_aircraft_life_limits"
down_revision: Union[str, Sequence[str], None] = "add_email_last_login"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("aircrafts", "type")
    op.drop_column("aircrafts", "airframe_model")
    op.drop_column("aircrafts", "airframe_serial_number")

    op.add_column(
        "aircrafts",
        sa.Column("engine_life_time_limit", sa.Float(), nullable=True),
    )
    op.add_column(
        "aircrafts",
        sa.Column("propeller_life_time_limit", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("aircrafts", "propeller_life_time_limit")
    op.drop_column("aircrafts", "engine_life_time_limit")

    op.add_column("aircrafts", sa.Column("airframe_serial_number", sa.String(), nullable=True))
    op.add_column("aircrafts", sa.Column("airframe_model", sa.String(), nullable=True))
    op.add_column("aircrafts", sa.Column("type", sa.String(), nullable=False))
