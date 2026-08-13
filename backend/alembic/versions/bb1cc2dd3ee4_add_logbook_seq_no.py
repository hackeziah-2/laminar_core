"""add logbook_seq_no to technical logbook tables

Revision ID: bb1cc2dd3ee4
Revises: aa0bb1cc2dd3
Create Date: 2026-08-13

Adds required logbook_seq_no (distinct from ATL sequence_no) to:
airframe_logbook, engine_logbook, avionics_logbook, propeller_logbook.

Existing rows are backfilled from sequence_no before NOT NULL is enforced.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "bb1cc2dd3ee4"
down_revision: Union[str, Sequence[str], None] = "aa0bb1cc2dd3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOGBOOK_TABLES = (
    "airframe_logbook",
    "engine_logbook",
    "avionics_logbook",
    "propeller_logbook",
)


def upgrade() -> None:
    for table_name in _LOGBOOK_TABLES:
        op.add_column(
            table_name,
            sa.Column("logbook_seq_no", sa.String(length=50), nullable=True),
        )
        # Prefer existing technical-logbook sequence_no for backfill.
        op.execute(
            f"""
            UPDATE {table_name}
            SET logbook_seq_no = NULLIF(TRIM(sequence_no), '')
            WHERE logbook_seq_no IS NULL
            """
        )
        # Fallback for any remaining blanks/nulls so NOT NULL can be applied safely.
        op.execute(
            f"""
            UPDATE {table_name}
            SET logbook_seq_no = 'LB-' || CAST(id AS VARCHAR)
            WHERE logbook_seq_no IS NULL OR TRIM(logbook_seq_no) = ''
            """
        )
        op.alter_column(
            table_name,
            "logbook_seq_no",
            existing_type=sa.String(length=50),
            nullable=False,
        )
        op.create_index(
            f"ix_{table_name}_logbook_seq_no",
            table_name,
            ["logbook_seq_no"],
            unique=False,
        )


def downgrade() -> None:
    for table_name in reversed(_LOGBOOK_TABLES):
        op.drop_index(f"ix_{table_name}_logbook_seq_no", table_name=table_name)
        op.drop_column(table_name, "logbook_seq_no")
