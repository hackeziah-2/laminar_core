"""add oem_item_types and oem_technical_publications tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oem_item_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
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
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oem_item_types_id"),
        "oem_item_types",
        ["id"],
        unique=False,
    )

    op.create_table(
        "oem_technical_publications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_fk", sa.Integer(), nullable=False),
        sa.Column("date_of_expiration", sa.Date(), nullable=True),
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
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["item_fk"], ["oem_item_types.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oem_technical_publications_id"),
        "oem_technical_publications",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oem_technical_publications_item_fk"),
        "oem_technical_publications",
        ["item_fk"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_oem_technical_publications_item_fk"),
        table_name="oem_technical_publications",
    )
    op.drop_index(
        op.f("ix_oem_technical_publications_id"),
        table_name="oem_technical_publications",
    )
    op.drop_table("oem_technical_publications")
    op.drop_index(
        op.f("ix_oem_item_types_id"),
        table_name="oem_item_types",
    )
    op.drop_table("oem_item_types")
