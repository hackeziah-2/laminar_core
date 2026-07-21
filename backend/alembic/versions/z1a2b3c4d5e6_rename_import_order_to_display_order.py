"""Rename import_order to display_order for TCC/CPCP

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-07-20

Environments that applied the first revision of y0z1a2b3c4d5 received
nullable ``import_order``. Application code expects non-nullable
``display_order``. This migration renames/backfills safely and is a
no-op when ``display_order`` already exists.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "y0z1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {col["name"] for col in inspect(bind).get_columns(table)}


def _indexes(table: str) -> set[str]:
    bind = op.get_bind()
    return {idx["name"] for idx in inspect(bind).get_indexes(table)}


def _migrate_table(table: str, partition_col: str) -> None:
    cols = _columns(table)
    idxs = _indexes(table)

    if "display_order" not in cols and "import_order" in cols:
        op.alter_column(table, "import_order", new_column_name="display_order")
        cols = _columns(table)
        idxs = _indexes(table)

    if "display_order" not in cols:
        op.add_column(table, sa.Column("display_order", sa.Integer(), nullable=True))

    # Backfill any nulls using current id order within the parent aircraft.
    op.execute(
        f"""
        WITH ordered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY {partition_col}
                    ORDER BY id ASC
                ) AS rn
            FROM {table}
        )
        UPDATE {table} AS t
        SET display_order = ordered.rn
        FROM ordered
        WHERE t.id = ordered.id
          AND (t.display_order IS NULL OR t.display_order < 1)
        """
    )

    op.alter_column(
        table,
        "display_order",
        existing_type=sa.Integer(),
        nullable=False,
    )

    old_idx = f"ix_{table}_import_order"
    new_idx = f"ix_{table}_display_order"
    idxs = _indexes(table)
    if old_idx in idxs:
        op.drop_index(old_idx, table_name=table)
        idxs = _indexes(table)
    if new_idx not in idxs:
        op.create_index(new_idx, table, ["display_order"], unique=False)

    # Drop leftover import_order if both columns somehow exist.
    cols = _columns(table)
    if "import_order" in cols and "display_order" in cols:
        leftover_idx = f"ix_{table}_import_order"
        if leftover_idx in _indexes(table):
            op.drop_index(leftover_idx, table_name=table)
        op.drop_column(table, "import_order")


def upgrade() -> None:
    _migrate_table("tcc_maintenance", "aircraft_fk")
    _migrate_table("cpcp_monitoring", "aircraft_id")


def downgrade() -> None:
    for table in ("cpcp_monitoring", "tcc_maintenance"):
        cols = _columns(table)
        idxs = _indexes(table)
        if "import_order" not in cols and "display_order" in cols:
            op.alter_column(table, "display_order", new_column_name="import_order")
            cols = _columns(table)
            idxs = _indexes(table)
        new_idx = f"ix_{table}_display_order"
        old_idx = f"ix_{table}_import_order"
        if new_idx in idxs:
            op.drop_index(new_idx, table_name=table)
            idxs = _indexes(table)
        if old_idx not in idxs and "import_order" in cols:
            op.create_index(old_idx, table, ["import_order"], unique=False)
        op.alter_column(
            table,
            "import_order",
            existing_type=sa.Integer(),
            nullable=True,
        )
