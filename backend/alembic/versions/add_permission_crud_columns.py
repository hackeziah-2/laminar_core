"""add can_create, can_update, can_delete to role and user permissions

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("role_permissions", "user_permissions"):
        op.add_column(
            table,
            sa.Column("can_create", sa.Boolean(), nullable=False, server_default="false"),
        )
        op.add_column(
            table,
            sa.Column("can_update", sa.Boolean(), nullable=False, server_default="false"),
        )
        op.add_column(
            table,
            sa.Column("can_delete", sa.Boolean(), nullable=False, server_default="false"),
        )
    op.execute(
        sa.text(
            """
            UPDATE role_permissions SET
                can_create = COALESCE(can_write, false),
                can_update = COALESCE(can_write, false),
                can_delete = COALESCE(can_write, false)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE user_permissions SET
                can_create = COALESCE(can_write, false),
                can_update = COALESCE(can_write, false),
                can_delete = COALESCE(can_write, false)
            """
        )
    )
    op.alter_column("role_permissions", "can_create", server_default=None)
    op.alter_column("role_permissions", "can_update", server_default=None)
    op.alter_column("role_permissions", "can_delete", server_default=None)
    op.alter_column("user_permissions", "can_create", server_default=None)
    op.alter_column("user_permissions", "can_update", server_default=None)
    op.alter_column("user_permissions", "can_delete", server_default=None)


def downgrade() -> None:
    for table in ("role_permissions", "user_permissions"):
        op.drop_column(table, "can_delete")
        op.drop_column(table, "can_update")
        op.drop_column(table, "can_create")
