"""add advisory notification logs table

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "q2r3s4t5u6v7"
down_revision: Union[str, Sequence[str], None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "advisory_notification_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("advisory_source_id", sa.Integer(), nullable=False),
        sa.Column("regulatory_compliance", sa.String(length=100), nullable=False),
        sa.Column("item", sa.String(length=255), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("notification_type", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_advisory_notification_logs_idempotency_key",
        ),
    )
    op.create_index(
        op.f("ix_advisory_notification_logs_id"),
        "advisory_notification_logs",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisory_notification_logs_advisory_source_id"),
        "advisory_notification_logs",
        ["advisory_source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisory_notification_logs_regulatory_compliance"),
        "advisory_notification_logs",
        ["regulatory_compliance"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisory_notification_logs_expiry_date"),
        "advisory_notification_logs",
        ["expiry_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisory_notification_logs_notification_type"),
        "advisory_notification_logs",
        ["notification_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisory_notification_logs_idempotency_key"),
        "advisory_notification_logs",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_advisory_notification_logs_idempotency_key"),
        table_name="advisory_notification_logs",
    )
    op.drop_index(
        op.f("ix_advisory_notification_logs_notification_type"),
        table_name="advisory_notification_logs",
    )
    op.drop_index(
        op.f("ix_advisory_notification_logs_expiry_date"),
        table_name="advisory_notification_logs",
    )
    op.drop_index(
        op.f("ix_advisory_notification_logs_regulatory_compliance"),
        table_name="advisory_notification_logs",
    )
    op.drop_index(
        op.f("ix_advisory_notification_logs_advisory_source_id"),
        table_name="advisory_notification_logs",
    )
    op.drop_index(
        op.f("ix_advisory_notification_logs_id"),
        table_name="advisory_notification_logs",
    )
    op.drop_table("advisory_notification_logs")
