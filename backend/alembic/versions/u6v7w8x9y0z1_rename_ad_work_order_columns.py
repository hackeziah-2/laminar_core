"""Rename AD work order actt/tach columns to aftt / next_due naming.

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u6v7w8x9y0z1"
down_revision: Union[str, Sequence[str], None] = "t5u6v7w8x9y0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("workorder_ad_monitoring")

    if "last_done_actt" in columns and "last_done_aftt" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "last_done_actt",
            new_column_name="last_done_aftt",
        )
        columns.remove("last_done_actt")
        columns.add("last_done_aftt")

    if "next_done_actt" in columns and "next_due_aftt" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_done_actt",
            new_column_name="next_due_aftt",
        )
        columns.remove("next_done_actt")
        columns.add("next_due_aftt")
    elif "next_done_aftt" in columns and "next_due_aftt" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_done_aftt",
            new_column_name="next_due_aftt",
        )
        columns.remove("next_done_aftt")
        columns.add("next_due_aftt")

    if "tach" in columns and "next_due_tach" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "tach",
            new_column_name="next_due_tach",
        )
    elif "next_done_tach" in columns and "next_due_tach" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_done_tach",
            new_column_name="next_due_tach",
        )


def downgrade() -> None:
    columns = _column_names("workorder_ad_monitoring")

    if "last_done_aftt" in columns and "last_done_actt" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "last_done_aftt",
            new_column_name="last_done_actt",
        )

    if "next_due_aftt" in columns and "next_done_actt" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_due_aftt",
            new_column_name="next_done_actt",
        )

    if "next_due_tach" in columns and "tach" not in columns:
        op.alter_column(
            "workorder_ad_monitoring",
            "next_due_tach",
            new_column_name="tach",
        )
