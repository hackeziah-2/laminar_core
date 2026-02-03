"""ldnd add unit and rename columns

Revision ID: ldnd_unit_rename
Revises: add_aircraft_fk_logbooks
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ldnd_unit_rename"
down_revision: Union[str, Sequence[str], None] = "add_aircraft_fk_logbooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename columns on ldnd_monitoring
    op.alter_column(
        "ldnd_monitoring",
        "date_performed_start",
        new_column_name="performed_date_start",
    )
    op.alter_column(
        "ldnd_monitoring",
        "date_performed_end",
        new_column_name="performed_date_end",
    )
    op.alter_column(
        "ldnd_monitoring",
        "next_due",
        new_column_name="next_due_tach_hours",
    )
    # Create enum and add unit column (PostgreSQL)
    op.execute("CREATE TYPE ldnd_unit AS ENUM ('HRS', 'CYCLES')")
    op.add_column(
        "ldnd_monitoring",
        sa.Column("unit", sa.Enum("HRS", "CYCLES", name="ldnd_unit", create_type=False), nullable=False, server_default="HRS"),
    )


def downgrade() -> None:
    op.drop_column("ldnd_monitoring", "unit")
    op.execute("DROP TYPE ldnd_unit")
    op.alter_column(
        "ldnd_monitoring",
        "performed_date_start",
        new_column_name="date_performed_start",
    )
    op.alter_column(
        "ldnd_monitoring",
        "performed_date_end",
        new_column_name="date_performed_end",
    )
    op.alter_column(
        "ldnd_monitoring",
        "next_due_tach_hours",
        new_column_name="next_due",
    )
