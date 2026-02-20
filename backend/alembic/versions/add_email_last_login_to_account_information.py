"""add email and last_login to account_information

Revision ID: add_email_last_login
Revises: add_rbac_tables
Create Date: 2025-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_email_last_login"
down_revision: Union[str, Sequence[str], None] = "add_rbac_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_information",
        sa.Column("email", sa.String(length=150), nullable=True),
    )
    op.create_index(
        op.f("ix_account_information_email"),
        "account_information",
        ["email"],
        unique=True,
    )

    op.add_column(
        "account_information",
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("account_information", "last_login")
    op.drop_index(op.f("ix_account_information_email"), table_name="account_information")
    op.drop_column("account_information", "email")
