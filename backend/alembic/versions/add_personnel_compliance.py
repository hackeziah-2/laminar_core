"""add personnel_compliance table

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-03-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    item_type_enum = postgresql.ENUM(
        "AUTH_EXPIRY",
        "CAAP_LICENSE",
        "HF_TRAINING",
        "CESSNA",
        "BARON",
        "OTHERS",
        name="personnel_compliance_item_type",
    )
    item_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "personnel_compliance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_information_id", sa.Integer(), nullable=False),
        sa.Column(
            "item_type",
            postgresql.ENUM(
                "AUTH_EXPIRY",
                "CAAP_LICENSE",
                "HF_TRAINING",
                "CESSNA",
                "BARON",
                "OTHERS",
                name="personnel_compliance_item_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("authorization_scope_cessna_id", sa.Integer(), nullable=True),
        sa.Column("authorization_scope_baron_id", sa.Integer(), nullable=True),
        sa.Column("authorization_scope_others_id", sa.Integer(), nullable=True),
        sa.Column("auth_issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("is_withhold", sa.Boolean(), server_default=sa.false(), nullable=False),
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
            ["account_information_id"],
            ["account_information.id"],
        ),
        sa.ForeignKeyConstraint(
            ["authorization_scope_baron_id"],
            ["authorization_scope_baron.id"],
        ),
        sa.ForeignKeyConstraint(
            ["authorization_scope_cessna_id"],
            ["authorization_scope_cessna.id"],
        ),
        sa.ForeignKeyConstraint(
            ["authorization_scope_others_id"],
            ["authorization_scope_others.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_personnel_compliance_id"),
        "personnel_compliance",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_compliance_account_information_id"),
        "personnel_compliance",
        ["account_information_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_compliance_item_type"),
        "personnel_compliance",
        ["item_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_compliance_authorization_scope_cessna_id"),
        "personnel_compliance",
        ["authorization_scope_cessna_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_compliance_authorization_scope_baron_id"),
        "personnel_compliance",
        ["authorization_scope_baron_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personnel_compliance_authorization_scope_others_id"),
        "personnel_compliance",
        ["authorization_scope_others_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_personnel_compliance_authorization_scope_others_id"),
        table_name="personnel_compliance",
    )
    op.drop_index(
        op.f("ix_personnel_compliance_authorization_scope_baron_id"),
        table_name="personnel_compliance",
    )
    op.drop_index(
        op.f("ix_personnel_compliance_authorization_scope_cessna_id"),
        table_name="personnel_compliance",
    )
    op.drop_index(
        op.f("ix_personnel_compliance_item_type"),
        table_name="personnel_compliance",
    )
    op.drop_index(
        op.f("ix_personnel_compliance_account_information_id"),
        table_name="personnel_compliance",
    )
    op.drop_index(
        op.f("ix_personnel_compliance_id"),
        table_name="personnel_compliance",
    )
    op.drop_table("personnel_compliance")
    item_type_enum = postgresql.ENUM(name="personnel_compliance_item_type")
    item_type_enum.drop(op.get_bind(), checkfirst=True)
