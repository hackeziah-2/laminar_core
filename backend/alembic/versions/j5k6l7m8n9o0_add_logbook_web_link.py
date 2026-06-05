"""add web_link to logbook tables

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-06-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "j5k6l7m8n9o0"
down_revision: Union[str, Sequence[str], None] = "i4j5k6l7m8n9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOGBOOK_TABLES = (
    "airframe_logbook",
    "engine_logbook",
    "propeller_logbook",
    "avionics_logbook",
)


def upgrade() -> None:
    for table_name in _LOGBOOK_TABLES:
        op.add_column(
            table_name,
            sa.Column("web_link", sa.String(length=2048), nullable=True),
        )


def downgrade() -> None:
    for table_name in reversed(_LOGBOOK_TABLES):
        op.drop_column(table_name, "web_link")
