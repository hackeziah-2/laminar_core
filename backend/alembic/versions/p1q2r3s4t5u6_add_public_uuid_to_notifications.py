"""add public uuid to notifications

Revision ID: p1q2r3s4t5u6
Revises: o0p1q2r3s4t5
Create Date: 2026-06-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, Sequence[str], None] = "o0p1q2r3s4t5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("notifications")}
    if "uuid" in column_names:
        return

    op.add_column(
        "notifications",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute("UPDATE notifications SET uuid = gen_random_uuid() WHERE uuid IS NULL")
    op.alter_column("notifications", "uuid", nullable=False)
    op.create_index("ix_notifications_uuid", "notifications", ["uuid"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("notifications")}
    if "uuid" not in column_names:
        return

    op.drop_index("ix_notifications_uuid", table_name="notifications")
    op.drop_column("notifications", "uuid")
