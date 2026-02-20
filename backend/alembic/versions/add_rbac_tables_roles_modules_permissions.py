"""add RBAC tables: roles, modules, role_permissions, user_permissions; add role_id to account_information

Revision ID: add_rbac_tables
Revises: add_atl_run_tsn_tbo
Create Date: 2025-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_rbac_tables"
down_revision: Union[str, Sequence[str], None] = "add_atl_run_tsn_tbo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create roles table
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_id"), "roles", ["id"], unique=False)
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    # Create modules table
    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_modules_id"), "modules", ["id"], unique=False)
    op.create_index(op.f("ix_modules_name"), "modules", ["name"], unique=True)

    # Add role_id to account_information (nullable to support existing rows)
    op.add_column(
        "account_information",
        sa.Column("role_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_account_information_role_id"),
        "account_information",
        ["role_id"],
        unique=False
    )
    op.create_foreign_key(
        "fk_account_information_role_id",
        "account_information",
        "roles",
        ["role_id"],
        ["id"],
    )

    # Create role_permissions table
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("can_read", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("can_write", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("can_approve", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"],),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "module_id", name="uq_role_module"),
    )
    op.create_index(op.f("ix_role_permissions_id"), "role_permissions", ["id"], unique=False)
    op.create_index(op.f("ix_role_permissions_role_id"), "role_permissions", ["role_id"], unique=False)
    op.create_index(op.f("ix_role_permissions_module_id"), "role_permissions", ["module_id"], unique=False)

    # Create user_permissions table
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("can_read", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("can_write", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("can_approve", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["account_id"], ["account_information.id"],),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "module_id", name="uq_account_module"),
    )
    op.create_index(op.f("ix_user_permissions_id"), "user_permissions", ["id"], unique=False)
    op.create_index(op.f("ix_user_permissions_account_id"), "user_permissions", ["account_id"], unique=False)
    op.create_index(op.f("ix_user_permissions_module_id"), "user_permissions", ["module_id"], unique=False)


def downgrade() -> None:
    # Drop user_permissions table
    op.drop_index(op.f("ix_user_permissions_module_id"), table_name="user_permissions")
    op.drop_index(op.f("ix_user_permissions_account_id"), table_name="user_permissions")
    op.drop_index(op.f("ix_user_permissions_id"), table_name="user_permissions")
    op.drop_table("user_permissions")

    # Drop role_permissions table
    op.drop_index(op.f("ix_role_permissions_module_id"), table_name="role_permissions")
    op.drop_index(op.f("ix_role_permissions_role_id"), table_name="role_permissions")
    op.drop_index(op.f("ix_role_permissions_id"), table_name="role_permissions")
    op.drop_table("role_permissions")

    # Remove role_id from account_information
    op.drop_constraint("fk_account_information_role_id", "account_information", type_="foreignkey")
    op.drop_index(op.f("ix_account_information_role_id"), table_name="account_information")
    op.drop_column("account_information", "role_id")

    # Drop modules table
    op.drop_index(op.f("ix_modules_name"), table_name="modules")
    op.drop_index(op.f("ix_modules_id"), table_name="modules")
    op.drop_table("modules")

    # Drop roles table
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_roles_id"), table_name="roles")
    op.drop_table("roles")
