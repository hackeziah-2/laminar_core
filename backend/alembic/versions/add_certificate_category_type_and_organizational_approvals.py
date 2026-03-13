"""add certificate_category_types and organizational_approvals tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "certificate_category_types",
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
        op.f("ix_certificate_category_types_id"),
        "certificate_category_types",
        ["id"],
        unique=False,
    )

    op.create_table(
        "organizational_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("certificate_fk", sa.Integer(), nullable=False),
        sa.Column("number", sa.Text(), nullable=True),
        sa.Column("date_of_expiration", sa.Date(), nullable=True),
        sa.Column("web_link", sa.String(length=2048), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
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
        sa.ForeignKeyConstraint(["certificate_fk"], ["certificate_category_types.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_organizational_approvals_id"),
        "organizational_approvals",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organizational_approvals_certificate_fk"),
        "organizational_approvals",
        ["certificate_fk"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_organizational_approvals_certificate_fk"),
        table_name="organizational_approvals",
    )
    op.drop_index(
        op.f("ix_organizational_approvals_id"),
        table_name="organizational_approvals",
    )
    op.drop_table("organizational_approvals")
    op.drop_index(
        op.f("ix_certificate_category_types_id"),
        table_name="certificate_category_types",
    )
    op.drop_table("certificate_category_types")
