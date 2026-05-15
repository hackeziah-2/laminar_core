"""Add atl_excel_import_job for ATL Excel import progress tracking.

Revision ID: f1a2b3c4d5e6
Revises: b7c8d9e0f1a2
Create Date: 2026-05-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "atl_excel_import_job",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "errors",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("temp_file_path", sa.Text(), nullable=True),
        sa.Column("aircraft_fk", sa.Integer(), nullable=False),
        sa.Column("atl_batch_fk", sa.Integer(), nullable=False),
        sa.Column("started_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["aircraft_fk"], ["aircrafts.id"]),
        sa.ForeignKeyConstraint(["atl_batch_fk"], ["atl_batch.id"]),
        sa.ForeignKeyConstraint(["started_by"], ["account_information.id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )


def downgrade() -> None:
    op.drop_table("atl_excel_import_job")
