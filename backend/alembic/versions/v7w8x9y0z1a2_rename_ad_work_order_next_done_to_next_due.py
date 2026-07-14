"""Rename AD work order next_done_* columns to next_due_*.

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-07-13

Handles databases where u6v7w8x9y0z1 was applied with intermediate
column names (next_done_aftt / next_done_tach) before the canonical
next_due_aftt / next_due_tach naming was finalized.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v7w8x9y0z1a2"
down_revision: Union[str, Sequence[str], None] = "u6v7w8x9y0z1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("workorder_ad_monitoring")
    if "next_done_aftt" in columns and "next_due_aftt" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_done_aftt",
            new_column_name="next_due_aftt",
        )
    if "next_done_tach" in columns and "next_due_tach" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_done_tach",
            new_column_name="next_due_tach",
        )


def downgrade() -> None:
    columns = _column_names("workorder_ad_monitoring")
    if "next_due_aftt" in columns and "next_done_aftt" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_due_aftt",
            new_column_name="next_done_aftt",
        )
    if "next_due_tach" in columns and "next_done_tach" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_due_tach",
            new_column_name="next_done_tach",
        )
