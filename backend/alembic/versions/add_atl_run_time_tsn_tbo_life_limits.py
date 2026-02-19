"""add ATL fields: airframe_run_time, airframe_aftt, engine_run_time/tsn/tso/tbo, propeller_run_time/tsn/tso/tbo, life_time_limit_engine/propeller

Revision ID: add_atl_run_tsn_tbo
Revises: atl_only_seq_ac_required
Create Date: 2025-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_atl_run_tsn_tbo"
down_revision: Union[str, Sequence[str], None] = "atl_only_seq_ac_required"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Airframe
    op.add_column("aircraft_technical_log", sa.Column("airframe_run_time", sa.Float(), nullable=True))
    op.add_column("aircraft_technical_log", sa.Column("airframe_aftt", sa.Float(), nullable=True))
    # Engine
    op.add_column("aircraft_technical_log", sa.Column("engine_run_time", sa.Float(), nullable=True))
    op.add_column("aircraft_technical_log", sa.Column("engine_tsn", sa.String(100), nullable=True))
    op.add_column("aircraft_technical_log", sa.Column("engine_tso", sa.Float(), nullable=True))
    op.add_column("aircraft_technical_log", sa.Column("engine_tbo", sa.Float(), nullable=True))
    # Propeller
    op.add_column("aircraft_technical_log", sa.Column("propeller_run_time", sa.Float(), nullable=True))
    op.add_column("aircraft_technical_log", sa.Column("propeller_tsn", sa.Float(), nullable=True))
    op.add_column("aircraft_technical_log", sa.Column("propeller_tso", sa.Float(), nullable=True))
    op.add_column("aircraft_technical_log", sa.Column("propeller_tbo", sa.Float(), nullable=True))
    # Life time limits
    op.add_column("aircraft_technical_log", sa.Column("life_time_limit_engine", sa.Float(), nullable=True))
    op.add_column("aircraft_technical_log", sa.Column("life_time_limit_propeller", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("aircraft_technical_log", "life_time_limit_propeller")
    op.drop_column("aircraft_technical_log", "life_time_limit_engine")
    op.drop_column("aircraft_technical_log", "propeller_tbo")
    op.drop_column("aircraft_technical_log", "propeller_tso")
    op.drop_column("aircraft_technical_log", "propeller_tsn")
    op.drop_column("aircraft_technical_log", "propeller_run_time")
    op.drop_column("aircraft_technical_log", "engine_tbo")
    op.drop_column("aircraft_technical_log", "engine_tso")
    op.drop_column("aircraft_technical_log", "engine_tsn")
    op.drop_column("aircraft_technical_log", "engine_run_time")
    op.drop_column("aircraft_technical_log", "airframe_aftt")
    op.drop_column("aircraft_technical_log", "airframe_run_time")
