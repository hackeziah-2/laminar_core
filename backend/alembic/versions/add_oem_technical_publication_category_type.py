"""add category_type to oem_technical_publications

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORY_TYPE_VALUES = (
    "CERTIFICATE",
    "SUBSCRIPTION",
    "REGULATORY_CORRESPONDENCE_NON_CERT",
    "LICENSE",
)


def upgrade() -> None:
    category_type_enum = postgresql.ENUM(
        *CATEGORY_TYPE_VALUES,
        name="oem_technical_publication_category_type",
        create_type=True,
    )
    category_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "oem_technical_publications",
        sa.Column(
            "category_type",
            postgresql.ENUM(
                *CATEGORY_TYPE_VALUES,
                name="oem_technical_publication_category_type",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    # Backfill existing rows with a default so we can make the column NOT NULL
    op.execute(
        f"""
        UPDATE oem_technical_publications
        SET category_type = 'CERTIFICATE'::oem_technical_publication_category_type
        WHERE category_type IS NULL
        """
    )
    op.alter_column(
        "oem_technical_publications",
        "category_type",
        existing_type=postgresql.ENUM(
            *CATEGORY_TYPE_VALUES,
            name="oem_technical_publication_category_type",
            create_type=False,
        ),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("oem_technical_publications", "category_type")
    op.execute("DROP TYPE IF EXISTS oem_technical_publication_category_type")
