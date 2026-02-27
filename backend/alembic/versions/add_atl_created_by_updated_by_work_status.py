"""add created_by, updated_by, work_status to aircraft_technical_log

Revision ID: add_atl_created_by_work_status
Revises: add_atl_repl_nature
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "add_atl_created_by_work_status"
down_revision: Union[str, Sequence[str], None] = "add_atl_repl_nature"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create work_status enum type
    work_status_enum = postgresql.ENUM(
        "FOR_REVIEW",
        "REJECTED_MAINTENANCE",
        "APPROVED",
        "AWAITING_ATTACHMENT",
        "REJECTED_QUALITY",
        "PENDING",
        "COMPLETED",
        name="work_status",
        create_type=True,
    )
    work_status_enum.create(op.get_bind(), checkfirst=True)

    # Add created_by column
    op.add_column(
        "aircraft_technical_log",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_atl_created_by_account",
        "aircraft_technical_log",
        "account_information",
        ["created_by"],
        ["id"],
    )

    # Add updated_by column
    op.add_column(
        "aircraft_technical_log",
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_atl_updated_by_account",
        "aircraft_technical_log",
        "account_information",
        ["updated_by"],
        ["id"],
    )

    # Add work_status column
    work_status_type = postgresql.ENUM(
        "FOR_REVIEW",
        "REJECTED_MAINTENANCE",
        "APPROVED",
        "AWAITING_ATTACHMENT",
        "REJECTED_QUALITY",
        "PENDING",
        "COMPLETED",
        name="work_status",
        create_type=False,
    )
    op.add_column(
        "aircraft_technical_log",
        sa.Column(
            "work_status",
            work_status_type,
            nullable=True,
            server_default=sa.text("'FOR_REVIEW'::work_status"),
        ),
    )


def downgrade() -> None:
    op.drop_column("aircraft_technical_log", "work_status")
    op.drop_constraint(
        "fk_atl_updated_by_account",
        "aircraft_technical_log",
        type_="foreignkey",
    )
    op.drop_column("aircraft_technical_log", "updated_by")
    op.drop_constraint(
        "fk_atl_created_by_account",
        "aircraft_technical_log",
        type_="foreignkey",
    )
    op.drop_column("aircraft_technical_log", "created_by")

    work_status_enum = postgresql.ENUM(name="work_status", create_type=False)
    work_status_enum.drop(op.get_bind(), checkfirst=True)
