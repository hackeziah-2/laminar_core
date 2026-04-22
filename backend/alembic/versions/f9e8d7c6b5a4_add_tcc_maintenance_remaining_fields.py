"""Add remaining_* float columns to tcc_maintenance

Revision ID: f9e8d7c6b5a4
Revises: f3a4b5c6d7e8
Create Date: 2026-04-20

Adds remaining_years, remaining_days, remaining_tach, remaining_aftt (FLOAT NOT NULL DEFAULT 0).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f9e8d7c6b5a4"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in (
        "remaining_years",
        "remaining_days",
        "remaining_tach",
        "remaining_aftt",
    ):
        op.add_column(
            "tcc_maintenance",
            sa.Column(col, sa.Float(), server_default="0", nullable=False),
        )


def downgrade() -> None:
    op.drop_column("tcc_maintenance", "remaining_aftt")
    op.drop_column("tcc_maintenance", "remaining_tach")
    op.drop_column("tcc_maintenance", "remaining_days")
    op.drop_column("tcc_maintenance", "remaining_years")
