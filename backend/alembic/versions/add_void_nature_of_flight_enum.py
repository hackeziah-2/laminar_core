"""Add VOID to nature_of_flight enum (ATL can be empty)

Revision ID: add_void_nature_of_flight
Revises: update_aircraft_life_limits
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op


revision: str = "add_void_nature_of_flight"
down_revision: Union[str, Sequence[str], None] = "update_aircraft_life_limits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE nature_of_flight ADD VALUE IF NOT EXISTS 'VOID'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; no-op
    pass
