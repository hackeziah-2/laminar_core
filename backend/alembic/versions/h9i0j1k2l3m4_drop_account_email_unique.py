"""Allow duplicate emails on account_information.

Revision ID: h9i0j1k2l3m4
Revises: g8b9c0d1e2f3
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op

revision: str = "h9i0j1k2l3m4"
down_revision: Union[str, Sequence[str], None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_account_information_email", table_name="account_information")
    op.create_index(
        "ix_account_information_email",
        "account_information",
        ["email"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_account_information_email", table_name="account_information")
    op.create_index(
        "ix_account_information_email",
        "account_information",
        ["email"],
        unique=True,
    )
