"""add file_path to ad_monitoring

Revision ID: add_file_path_ad_monitoring
Revises: drop_part_desc_component
Create Date: 2026-02-06

Adds file_path column to ad_monitoring table for file uploads.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_file_path_ad_monitoring"
down_revision: Union[str, Sequence[str], None] = "drop_part_desc_component"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ad_monitoring",
        sa.Column("file_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ad_monitoring", "file_path")
