"""ATL numeric columns use NUMERIC(20,10) for exact import precision

Revision ID: c2d3e4f5a6b7
Revises: z1a2b3c4d5e6
Create Date: 2026-07-20

Preserve Excel decimal digits for ATL Operation import without float rounding.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ATL_NUMERIC = sa.Numeric(20, 10)

_ATL_COLUMNS = (
    "tach_time_due",
    "hobbs_meter_start",
    "hobbs_meter_end",
    "hobbs_meter_total",
    "tachometer_start",
    "tachometer_end",
    "tachometer_total",
    "airframe_prev_time",
    "airframe_flight_time",
    "airframe_total_time",
    "airframe_run_time",
    "airframe_aftt",
    "engine_prev_time",
    "engine_flight_time",
    "engine_total_time",
    "engine_run_time",
    "engine_tso",
    "engine_tbo",
    "propeller_prev_time",
    "propeller_flight_time",
    "propeller_total_time",
    "propeller_run_time",
    "propeller_tsn",
    "propeller_tso",
    "propeller_tbo",
    "life_time_limit_engine",
    "life_time_limit_propeller",
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
    "fuel_qty_left_uplift_qty",
    "fuel_qty_right_uplift_qty",
    "fuel_qty_left_prior_departure",
    "fuel_qty_right_prior_departure",
    "fuel_qty_left_after_on_blks",
    "fuel_qty_right_after_on_blks",
    "oil_qty_uplift_qty",
    "oil_qty_prior_departure",
    "oil_qty_after_on_blks",
)


def upgrade() -> None:
    for column in _ATL_COLUMNS:
        op.alter_column(
            "aircraft_technical_log",
            column,
            existing_type=sa.Float(),
            type_=_ATL_NUMERIC,
            postgresql_using=f"{column}::numeric(20,10)",
        )
    op.alter_column(
        "component_parts_record",
        "qty",
        existing_type=sa.Float(),
        type_=_ATL_NUMERIC,
        postgresql_using="qty::numeric(20,10)",
    )


def downgrade() -> None:
    for column in _ATL_COLUMNS:
        op.alter_column(
            "aircraft_technical_log",
            column,
            existing_type=_ATL_NUMERIC,
            type_=sa.Float(),
            postgresql_using=f"{column}::double precision",
        )
    op.alter_column(
        "component_parts_record",
        "qty",
        existing_type=_ATL_NUMERIC,
        type_=sa.Float(),
        postgresql_using="qty::double precision",
    )
