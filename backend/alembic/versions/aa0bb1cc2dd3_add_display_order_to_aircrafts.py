"""Add display_order to aircrafts

Revision ID: aa0bb1cc2dd3
Revises: c2d3e4f5a6b7
Create Date: 2026-07-24

Persistent drag-and-drop row order shared by Aircraft Fleet Profile and
Aircraft Fleet Daily Update. Existing active rows are backfilled globally
using current id order (1..N). Soft-deleted rows also receive sequential
orders so the column can be NOT NULL.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "aa0bb1cc2dd3"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aircrafts",
        sa.Column("display_order", sa.Integer(), nullable=True),
    )
    # Active aircraft first (global 1..N by id), then soft-deleted (continue sequence).
    op.execute(
        """
        WITH ordered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    ORDER BY
                        CASE WHEN is_deleted IS FALSE THEN 0 ELSE 1 END,
                        id ASC
                ) AS rn
            FROM aircrafts
        )
        UPDATE aircrafts AS a
        SET display_order = ordered.rn
        FROM ordered
        WHERE a.id = ordered.id
        """
    )
    op.alter_column(
        "aircrafts",
        "display_order",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        op.f("ix_aircrafts_display_order"),
        "aircrafts",
        ["display_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_aircrafts_display_order"), table_name="aircrafts")
    op.drop_column("aircrafts", "display_order")
