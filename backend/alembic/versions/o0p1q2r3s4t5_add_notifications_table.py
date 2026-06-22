"""add notifications table

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-06-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "o0p1q2r3s4t5"
down_revision: Union[str, Sequence[str], None] = "n9o0p1q2r3s4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOTIFICATION_TYPE_VALUES = ("SYSTEM", "APPROVAL", "REMINDER", "ALERT", "INFO")
NOTIFICATION_SEVERITY_VALUES = ("INFO", "SUCCESS", "WARNING", "CRITICAL")
NOTIFICATION_STATUS_VALUES = ("UNREAD", "READ", "ARCHIVED")


def upgrade() -> None:
    notification_type_enum = postgresql.ENUM(
        *NOTIFICATION_TYPE_VALUES,
        name="notification_type_enum",
    )
    notification_severity_enum = postgresql.ENUM(
        *NOTIFICATION_SEVERITY_VALUES,
        name="notification_severity_enum",
    )
    notification_status_enum = postgresql.ENUM(
        *NOTIFICATION_STATUS_VALUES,
        name="notification_status_enum",
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)
    notification_severity_enum.create(op.get_bind(), checkfirst=True)
    notification_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "uuid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("recipient_account_id", sa.Integer(), nullable=False),
        sa.Column("sender_account_id", sa.Integer(), nullable=True),
        sa.Column("sender_initials", sa.String(length=5), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("module_name", sa.String(length=100), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                *NOTIFICATION_TYPE_VALUES,
                name="notification_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM(
                *NOTIFICATION_SEVERITY_VALUES,
                name="notification_severity_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                *NOTIFICATION_STATUS_VALUES,
                name="notification_status_enum",
                create_type=False,
            ),
            server_default="UNREAD",
            nullable=False,
        ),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("reference_type", sa.String(length=100), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["recipient_account_id"],
            ["account_information.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sender_account_id"],
            ["account_information.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index("ix_notifications_uuid", "notifications", ["uuid"], unique=True)
    op.create_index(
        op.f("ix_notifications_recipient_account_id"),
        "notifications",
        ["recipient_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_sender_account_id"),
        "notifications",
        ["sender_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_module_name"),
        "notifications",
        ["module_name"],
        unique=False,
    )
    op.create_index(op.f("ix_notifications_type"), "notifications", ["type"], unique=False)
    op.create_index(
        op.f("ix_notifications_severity"),
        "notifications",
        ["severity"],
        unique=False,
    )
    op.create_index(op.f("ix_notifications_status"), "notifications", ["status"], unique=False)
    op.create_index(
        op.f("ix_notifications_reference_id"),
        "notifications",
        ["reference_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_reference_type"),
        "notifications",
        ["reference_type"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_recipient_status_created",
        "notifications",
        ["recipient_account_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_recipient_status_created", table_name="notifications")
    op.drop_index(op.f("ix_notifications_reference_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_reference_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_status"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_severity"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_module_name"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_sender_account_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_recipient_account_id"), table_name="notifications")
    op.drop_index("ix_notifications_uuid", table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")

    notification_status_enum = postgresql.ENUM(name="notification_status_enum")
    notification_severity_enum = postgresql.ENUM(name="notification_severity_enum")
    notification_type_enum = postgresql.ENUM(name="notification_type_enum")
    notification_status_enum.drop(op.get_bind(), checkfirst=True)
    notification_severity_enum.drop(op.get_bind(), checkfirst=True)
    notification_type_enum.drop(op.get_bind(), checkfirst=True)
