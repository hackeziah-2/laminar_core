"""TCC Maintenance: nullable computed float columns

Revision ID: c1d2e3f4a5b0
Revises: e0f1a2b3c4d5
Create Date: 2026-04-20

Allows NULL for server-computed fields when formulas do not apply.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c1d2e3f4a5b0"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NULLABLE_FLOATS = (
    "remaining_years",
    "remaining_days",
    "remaining_tach",
    "remaining_aftt",
    "next_due_tach",
    "next_due_aftt",
)


def upgrade() -> None:
    for col in _NULLABLE_FLOATS:
        op.alter_column(
            "tcc_maintenance",
            col,
            existing_type=sa.Float(),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    for col in _NULLABLE_FLOATS:
        op.execute(
            f"UPDATE tcc_maintenance SET {col} = 0 WHERE {col} IS NULL"
        )
    for col in _NULLABLE_FLOATS:
        op.alter_column(
            "tcc_maintenance",
            col,
            existing_type=sa.Float(),
            nullable=False,
            server_default="0",
        )
