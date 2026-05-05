"""add oa_history FK to organizational_approvals_history

Revision ID: a9b8c7d6e5f4
Revises: f8e9d0c1b2a3
Create Date: 2026-03-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "f8e9d0c1b2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizational_approvals_history",
        sa.Column("oa_history", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_organizational_approvals_history_oa_history",
        "organizational_approvals_history",
        "organizational_approvals",
        ["oa_history"],
        ["id"],
    )
    op.create_index(
        op.f("ix_organizational_approvals_history_oa_history"),
        "organizational_approvals_history",
        ["oa_history"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_organizational_approvals_history_oa_history"),
        table_name="organizational_approvals_history",
    )
    op.drop_constraint(
        "fk_organizational_approvals_history_oa_history",
        "organizational_approvals_history",
        type_="foreignkey",
    )
    op.drop_column("organizational_approvals_history", "oa_history")
