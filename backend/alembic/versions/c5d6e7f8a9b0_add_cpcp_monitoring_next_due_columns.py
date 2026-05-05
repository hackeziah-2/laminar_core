"""Add next_due_* columns to cpcp_monitoring

Revision ID: c5d6e7f8a9b0
Revises: c1d2e3f4a5b0
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cpcp_monitoring", sa.Column("next_due_tach", sa.Float(), nullable=True))
    op.add_column("cpcp_monitoring", sa.Column("next_due_aftt", sa.Float(), nullable=True))
    op.add_column("cpcp_monitoring", sa.Column("next_due_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("cpcp_monitoring", "next_due_date")
    op.drop_column("cpcp_monitoring", "next_due_aftt")
    op.drop_column("cpcp_monitoring", "next_due_tach")
