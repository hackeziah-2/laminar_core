"""make tcc_maintenance.atl_ref nullable

Revision ID: make_tcc_atl_ref_nullable
Revises: add_tcc_category_enum
Create Date: 2026-02-10

Makes atl_ref optional (nullable) on tcc_maintenance.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "make_tcc_atl_ref_nullable"
down_revision: Union[str, Sequence[str], None] = "add_tcc_category_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tcc_maintenance",
        "atl_ref",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "tcc_maintenance",
        "atl_ref",
        existing_type=sa.Integer(),
        nullable=False,
    )
