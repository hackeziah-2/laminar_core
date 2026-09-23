"""Owner-scoped upload metadata and duplicate protection.

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
"""
from alembic import op
import sqlalchemy as sa
revision = 'i0j1k2l3m4n5'
down_revision = 'h9i0j1k2l3m4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('upload_assets',
        sa.Column('file_path', sa.String(500), primary_key=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('account_information.id'), nullable=False),
        sa.Column('module_folder', sa.String(80), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('original_filename', sa.String(1024), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('content_type', sa.String(120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('owner_id', 'module_folder', 'sha256', name='uq_upload_owner_module_sha256'))


def downgrade():
    op.drop_table('upload_assets')
