"""Add ATL_REPL to nature_of_flight enum

Revision ID: add_atl_repl_nature
Revises: add_void_nature_of_flight
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op


revision: str = "add_atl_repl_nature"
down_revision: Union[str, Sequence[str], None] = "add_void_nature_of_flight"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE cannot run inside a transaction block in PostgreSQL; use autocommit
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE nature_of_flight ADD VALUE IF NOT EXISTS 'ATL_REPL'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; no-op
    pass
