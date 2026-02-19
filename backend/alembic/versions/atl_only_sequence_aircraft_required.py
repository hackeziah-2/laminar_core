"""ATL: only sequence_no and aircraft_fk required (other columns nullable)

Revision ID: atl_only_seq_ac_required
Revises: add_aircraft_id_cpcp
Create Date: 2026-02-17

Makes aircraft_technical_log columns nullable except aircraft_fk and sequence_no.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


revision: str = "atl_only_seq_ac_required"
down_revision: Union[str, Sequence[str], None] = "add_aircraft_id_cpcp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PostgreSQL enum for nature_of_flight (existing type, do not create)
NATURE_ENUM = ENUM("TR", "PSF", "PRF", "EGR", "ME", "TR_WITH_PIREM", name="nature_of_flight", create_type=False)


def upgrade() -> None:
    table = "aircraft_technical_log"
    # Columns to make nullable (aircraft_fk and sequence_no stay NOT NULL)
    op.alter_column(table, "nature_of_flight", existing_type=NATURE_ENUM, nullable=True)
    op.alter_column(table, "next_inspection_due", existing_type=sa.String(100), nullable=True)
    op.alter_column(table, "tach_time_due", existing_type=sa.Float(), nullable=True)
    op.alter_column(table, "origin_station", existing_type=sa.String(50), nullable=True)
    op.alter_column(table, "origin_date", existing_type=sa.Date(), nullable=True)
    op.alter_column(table, "origin_time", existing_type=sa.Time(), nullable=True)
    op.alter_column(table, "destination_station", existing_type=sa.String(50), nullable=True)
    op.alter_column(table, "destination_date", existing_type=sa.Date(), nullable=True)
    op.alter_column(table, "destination_time", existing_type=sa.Time(), nullable=True)
    op.alter_column(table, "number_of_landings", existing_type=sa.Integer(), nullable=True)
    op.alter_column(table, "hobbs_meter_start", existing_type=sa.Float(), nullable=True)
    op.alter_column(table, "hobbs_meter_end", existing_type=sa.Float(), nullable=True)
    op.alter_column(table, "hobbs_meter_total", existing_type=sa.Float(), nullable=True)
    op.alter_column(table, "tachometer_start", existing_type=sa.Float(), nullable=True)
    op.alter_column(table, "tachometer_end", existing_type=sa.Float(), nullable=True)
    op.alter_column(table, "tachometer_total", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    table = "aircraft_technical_log"
    # Revert to NOT NULL (will fail if any row has NULL in these columns)
    op.alter_column(table, "nature_of_flight", existing_type=NATURE_ENUM, nullable=False)
    op.alter_column(table, "next_inspection_due", existing_type=sa.String(100), nullable=False)
    op.alter_column(table, "tach_time_due", existing_type=sa.Float(), nullable=False)
    op.alter_column(table, "origin_station", existing_type=sa.String(50), nullable=False)
    op.alter_column(table, "origin_date", existing_type=sa.Date(), nullable=False)
    op.alter_column(table, "origin_time", existing_type=sa.Time(), nullable=False)
    op.alter_column(table, "destination_station", existing_type=sa.String(50), nullable=False)
    op.alter_column(table, "destination_date", existing_type=sa.Date(), nullable=False)
    op.alter_column(table, "destination_time", existing_type=sa.Time(), nullable=False)
    op.alter_column(table, "number_of_landings", existing_type=sa.Integer(), nullable=False)
    op.alter_column(table, "hobbs_meter_start", existing_type=sa.Float(), nullable=False)
    op.alter_column(table, "hobbs_meter_end", existing_type=sa.Float(), nullable=False)
    op.alter_column(table, "hobbs_meter_total", existing_type=sa.Float(), nullable=False)
    op.alter_column(table, "tachometer_start", existing_type=sa.Float(), nullable=False)
    op.alter_column(table, "tachometer_end", existing_type=sa.Float(), nullable=False)
    op.alter_column(table, "tachometer_total", existing_type=sa.Float(), nullable=False)
