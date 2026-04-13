"""add web_link to oem_technical_publications

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "oem_technical_publications",
        sa.Column("web_link", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("oem_technical_publications", "web_link")
