"""add web_link to ad_monitoring

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-06-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i4j5k6l7m8n9"
down_revision: Union[str, Sequence[str], None] = "h3i4j5k6l7m8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ad_monitoring",
        sa.Column("web_link", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ad_monitoring", "web_link")
