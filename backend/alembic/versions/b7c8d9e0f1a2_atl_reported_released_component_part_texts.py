"""ATL date_time_reported/released; component part remaining time / remark

Revision ID: b7c8d9e0f1a2
Revises: e4f5a6b7c8d9
Create Date: 2026-05-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aircraft_technical_log",
        sa.Column("date_time_reported", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "aircraft_technical_log",
        sa.Column("date_time_released", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "component_parts_record",
        sa.Column("part_installed_remaining_time", sa.Text(), nullable=True),
    )
    op.add_column(
        "component_parts_record",
        sa.Column("part_removed_remaining_time", sa.Text(), nullable=True),
    )
    op.add_column(
        "component_parts_record",
        sa.Column("part_remark", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("component_parts_record", "part_remark")
    op.drop_column("component_parts_record", "part_removed_remaining_time")
    op.drop_column("component_parts_record", "part_installed_remaining_time")
    op.drop_column("aircraft_technical_log", "date_time_released")
    op.drop_column("aircraft_technical_log", "date_time_reported")
