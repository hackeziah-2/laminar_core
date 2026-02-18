"""add aircraft_id to cpcp_monitoring (required)

Revision ID: add_aircraft_id_cpcp
Revises: create_cpcp_monitoring
Create Date: 2026-02-17

Add required aircraft_id FK to cpcp_monitoring.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_aircraft_id_cpcp"
down_revision: Union[str, Sequence[str], None] = "create_cpcp_monitoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cpcp_monitoring", sa.Column("aircraft_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_cpcp_monitoring_aircraft_id",
        "cpcp_monitoring",
        "aircrafts",
        ["aircraft_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_cpcp_monitoring_aircraft_id"), "cpcp_monitoring", ["aircraft_id"], unique=False)
    # Backfill existing rows with first aircraft, then make column required
    op.execute(
        "UPDATE cpcp_monitoring SET aircraft_id = (SELECT id FROM aircrafts LIMIT 1) WHERE aircraft_id IS NULL"
    )
    op.alter_column(
        "cpcp_monitoring",
        "aircraft_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cpcp_monitoring_aircraft_id"), table_name="cpcp_monitoring")
    op.drop_constraint("fk_cpcp_monitoring_aircraft_id", "cpcp_monitoring", type_="foreignkey")
    op.drop_column("cpcp_monitoring", "aircraft_id")
