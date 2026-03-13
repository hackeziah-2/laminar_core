"""add authorization_scope_* and personnel_authorization tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "authorization_scope_cessna",
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
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_authorization_scope_cessna_id"),
        "authorization_scope_cessna",
        ["id"],
        unique=False,
    )

    op.create_table(
        "authorization_scope_baron",
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
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_authorization_scope_baron_id"),
        "authorization_scope_baron",
        ["id"],
        unique=False,
    )

    op.create_table(
        "authorization_scope_others",
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
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_authorization_scope_others_id"),
        "authorization_scope_others",
        ["id"],
        unique=False,
    )

    op.create_table(
        "personnel_authorization",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_information_id", sa.Integer(), nullable=False),
        sa.Column("authorization_scope_cessna_id", sa.Integer(), nullable=True),
        sa.Column("authorization_scope_baron_id", sa.Integer(), nullable=True),
        sa.Column("authorization_scope_others_id", sa.Integer(), nullable=True),
        sa.Column("auth_initial_doi", sa.Date(), nullable=True),
        sa.Column("auth_issue_date", sa.Date(), nullable=True),
        sa.Column("auth_expiry_date", sa.Date(), nullable=True),
        sa.Column("caap_license_expiry", sa.Date(), nullable=True),
        sa.Column("human_factors_training_expiry", sa.Date(), nullable=True),
        sa.Column("type_training_expiry_cessna", sa.Date(), nullable=True),
        sa.Column("type_training_expiry_baron", sa.Date(), nullable=True),
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
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_information_id"], ["account_information.id"]
        ),
        sa.ForeignKeyConstraint(
            ["authorization_scope_cessna_id"], ["authorization_scope_cessna.id"]
        ),
        sa.ForeignKeyConstraint(
            ["authorization_scope_baron_id"], ["authorization_scope_baron.id"]
        ),
        sa.ForeignKeyConstraint(
            ["authorization_scope_others_id"], ["authorization_scope_others.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_personnel_authorization_id"),
        "personnel_authorization",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_authorization_account_information_id"),
        "personnel_authorization",
        ["account_information_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_authorization_authorization_scope_cessna_id"),
        "personnel_authorization",
        ["authorization_scope_cessna_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_authorization_authorization_scope_baron_id"),
        "personnel_authorization",
        ["authorization_scope_baron_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_authorization_authorization_scope_others_id"),
        "personnel_authorization",
        ["authorization_scope_others_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_personnel_authorization_authorization_scope_others_id"),
        table_name="personnel_authorization",
    )
    op.drop_index(
        op.f("ix_personnel_authorization_authorization_scope_baron_id"),
        table_name="personnel_authorization",
    )
    op.drop_index(
        op.f("ix_personnel_authorization_authorization_scope_cessna_id"),
        table_name="personnel_authorization",
    )
    op.drop_index(
        op.f("ix_personnel_authorization_account_information_id"),
        table_name="personnel_authorization",
    )
    op.drop_index(
        op.f("ix_personnel_authorization_id"),
        table_name="personnel_authorization",
    )
    op.drop_table("personnel_authorization")
    op.drop_index(
        op.f("ix_authorization_scope_others_id"),
        table_name="authorization_scope_others",
    )
    op.drop_table("authorization_scope_others")
    op.drop_index(
        op.f("ix_authorization_scope_baron_id"),
        table_name="authorization_scope_baron",
    )
    op.drop_table("authorization_scope_baron")
    op.drop_index(
        op.f("ix_authorization_scope_cessna_id"),
        table_name="authorization_scope_cessna",
    )
    op.drop_table("authorization_scope_cessna")
