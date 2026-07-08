"""Optional import_summary column and ATL upsert index.

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-06-30

Summary is also embedded in atl_excel_import_job.message for environments
that have not applied this migration; the column is optional.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r3s4t5u6v7w8"
down_revision: Union[str, Sequence[str], None] = "q2r3s4t5u6v7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_atl_import_upsert_lookup
        ON aircraft_technical_log (aircraft_fk, atl_batch_fk, sequence_no)
        WHERE is_deleted IS FALSE
        """
    )
    # Optional: summary JSON column (app also embeds summary in message).
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {c["name"] for c in inspector.get_columns("atl_excel_import_job")}
    if "import_summary" not in columns:
        op.add_column(
            "atl_excel_import_job",
            sa.Column("import_summary", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_atl_import_upsert_lookup")
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {c["name"] for c in inspector.get_columns("atl_excel_import_job")}
    if "import_summary" in columns:
        op.drop_column("atl_excel_import_job", "import_summary")
