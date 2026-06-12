"""Convert naive datetime columns to timestamptz (PH time standard)

Legacy columns were populated with naive UTC values (datetime.utcnow).
Convert them to timestamptz interpreting existing data as UTC, so the
stored instants stay correct and render in Asia/Manila going forward.

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-06-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n9o0p1q2r3s4"
down_revision: Union[str, Sequence[str], None] = "m8n9o0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("users", "created_at"),
    ("flights", "departure_time"),
    ("flights", "arrival_time"),
)


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=False),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
