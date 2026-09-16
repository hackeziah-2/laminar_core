"""Add authorization_scope_piper_pa34 and personnel FKs.

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "authorization_scope_piper_pa34",
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
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["account_information.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["account_information.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_authorization_scope_piper_pa34_id"),
        "authorization_scope_piper_pa34",
        ["id"],
        unique=False,
    )

    op.add_column(
        "personnel_authorization",
        sa.Column("authorization_scope_piper_pa34_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_personnel_authorization_authorization_scope_piper_pa34_id"),
        "personnel_authorization",
        ["authorization_scope_piper_pa34_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_personnel_authorization_authorization_scope_piper_pa34_id"),
        "personnel_authorization",
        "authorization_scope_piper_pa34",
        ["authorization_scope_piper_pa34_id"],
        ["id"],
    )

    op.add_column(
        "personnel_compliance",
        sa.Column("authorization_scope_piper_pa34_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_personnel_compliance_authorization_scope_piper_pa34_id"),
        "personnel_compliance",
        ["authorization_scope_piper_pa34_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_personnel_compliance_authorization_scope_piper_pa34_id"),
        "personnel_compliance",
        "authorization_scope_piper_pa34",
        ["authorization_scope_piper_pa34_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_personnel_compliance_authorization_scope_piper_pa34_id"),
        "personnel_compliance",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_personnel_compliance_authorization_scope_piper_pa34_id"),
        table_name="personnel_compliance",
    )
    op.drop_column("personnel_compliance", "authorization_scope_piper_pa34_id")

    op.drop_constraint(
        op.f("fk_personnel_authorization_authorization_scope_piper_pa34_id"),
        "personnel_authorization",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_personnel_authorization_authorization_scope_piper_pa34_id"),
        table_name="personnel_authorization",
    )
    op.drop_column(
        "personnel_authorization", "authorization_scope_piper_pa34_id"
    )

    op.drop_index(
        op.f("ix_authorization_scope_piper_pa34_id"),
        table_name="authorization_scope_piper_pa34",
    )
    op.drop_table("authorization_scope_piper_pa34")
