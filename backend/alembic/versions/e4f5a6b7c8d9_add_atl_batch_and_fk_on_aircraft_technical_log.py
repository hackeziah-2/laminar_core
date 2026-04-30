"""Add atl_batch table and atl_batch_fk on aircraft_technical_log.

Revision ID: e4f5a6b7c8d9
Revises: d1e2f3a4b5c6
Create Date: 2026-04-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "atl_batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["account_information.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["account_information.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_atl_batch_id"), "atl_batch", ["id"], unique=False)
    op.add_column(
        "aircraft_technical_log",
        sa.Column("atl_batch_fk", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_aircraft_technical_log_atl_batch_fk_atl_batch"),
        "aircraft_technical_log",
        "atl_batch",
        ["atl_batch_fk"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_aircraft_technical_log_atl_batch_fk_atl_batch"),
        "aircraft_technical_log",
        type_="foreignkey",
    )
    op.drop_column("aircraft_technical_log", "atl_batch_fk")
    op.drop_index(op.f("ix_atl_batch_id"), table_name="atl_batch")
    op.drop_table("atl_batch")
