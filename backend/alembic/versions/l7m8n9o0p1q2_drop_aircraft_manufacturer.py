"""Drop aircrafts.manufacturer column.

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-06-09 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l7m8n9o0p1q2"
down_revision: Union[str, Sequence[str], None] = "k6l7m8n9o0p1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_aircrafts_manufacturer"), table_name="aircrafts")
    op.drop_column("aircrafts", "manufacturer")


def downgrade() -> None:
    op.add_column(
        "aircrafts",
        sa.Column("manufacturer", sa.String(length=89), nullable=False, server_default="N/A"),
    )
    op.alter_column("aircrafts", "manufacturer", server_default=None)
    op.create_index(op.f("ix_aircrafts_manufacturer"), "aircrafts", ["manufacturer"], unique=False)
