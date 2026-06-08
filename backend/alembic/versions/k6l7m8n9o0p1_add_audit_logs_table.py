"""add audit_logs table

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-06-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k6l7m8n9o0p1"
down_revision: Union[str, Sequence[str], None] = "j5k6l7m8n9o0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module_name", sa.String(length=100), nullable=False),
        sa.Column("table_name", sa.String(length=100), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("old_data", sa.JSON(), nullable=True),
        sa.Column("new_data", sa.JSON(), nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("performed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("performed_by_name", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"],
            ["account_information.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_module_name"),
        "audit_logs",
        ["module_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_table_name"),
        "audit_logs",
        ["table_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_record_id"),
        "audit_logs",
        ["record_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_action"),
        "audit_logs",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_performed_by_user_id"),
        "audit_logs",
        ["performed_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_created_at"),
        "audit_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(
        op.f("ix_audit_logs_performed_by_user_id"),
        table_name="audit_logs",
    )
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_record_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_table_name"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_module_name"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
