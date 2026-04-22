"""Add next_due_* columns to tcc_maintenance

Revision ID: e0f1a2b3c4d5
Revises: f9e8d7c6b5a4
Create Date: 2026-04-20

Adds next_due_date (DATE NULL), next_due_tach and next_due_aftt (FLOAT NOT NULL DEFAULT 0).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "f9e8d7c6b5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tcc_maintenance", sa.Column("next_due_date", sa.Date(), nullable=True))
    op.add_column(
        "tcc_maintenance",
        sa.Column("next_due_tach", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "tcc_maintenance",
        sa.Column("next_due_aftt", sa.Float(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tcc_maintenance", "next_due_aftt")
    op.drop_column("tcc_maintenance", "next_due_tach")
    op.drop_column("tcc_maintenance", "next_due_date")
