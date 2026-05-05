"""add organizational_approvals_history and aircraft_statutory_certificates_history

Revision ID: e7f8a9b0c1d2
Revises: b4c5d6e7f8a9
Create Date: 2026-03-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORY_VALUES = (
    "COA",
    "COR",
    "NTC",
    "PITOT_STATIC",
    "TRANSPONDER",
    "ELT",
    "WEIGHT_BALANCE",
    "COMPASS_SWING",
    "MARKING_RESERVATION",
    "BINARY_CODE_24BIT",
    "IBRD_CORPAS",
)


def upgrade() -> None:
    op.create_table(
        "organizational_approvals_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("certificate_fk", sa.Integer(), nullable=False),
        sa.Column("number", sa.Text(), nullable=True),
        sa.Column("date_of_expiration", sa.Date(), nullable=True),
        sa.Column("web_link", sa.String(length=2048), nullable=True),
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
        sa.ForeignKeyConstraint(["certificate_fk"], ["certificate_category_types.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_organizational_approvals_history_id"),
        "organizational_approvals_history",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organizational_approvals_history_certificate_fk"),
        "organizational_approvals_history",
        ["certificate_fk"],
        unique=False,
    )

    op.create_table(
        "aircraft_statutory_certificates_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aircraft_fk", sa.Integer(), nullable=False),
        sa.Column(
            "category_type",
            postgresql.ENUM(
                *CATEGORY_VALUES,
                name="statutory_certificate_category_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("date_of_expiration", sa.Date(), nullable=True),
        sa.Column("web_link", sa.String(length=2048), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_aircraft_statutory_certificates_history_id"),
        "aircraft_statutory_certificates_history",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_aircraft_statutory_certificates_history_aircraft_fk"),
        "aircraft_statutory_certificates_history",
        ["aircraft_fk"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_aircraft_statutory_certificates_history_aircraft_fk"),
        table_name="aircraft_statutory_certificates_history",
    )
    op.drop_index(
        op.f("ix_aircraft_statutory_certificates_history_id"),
        table_name="aircraft_statutory_certificates_history",
    )
    op.drop_table("aircraft_statutory_certificates_history")

    op.drop_index(
        op.f("ix_organizational_approvals_history_certificate_fk"),
        table_name="organizational_approvals_history",
    )
    op.drop_index(
        op.f("ix_organizational_approvals_history_id"),
        table_name="organizational_approvals_history",
    )
    op.drop_table("organizational_approvals_history")
