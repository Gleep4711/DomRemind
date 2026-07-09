"""add source column to user_domains

Revision ID: 007
Revises: 006
"""

from alembic import op
import sqlalchemy as sa


revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'user_domains',
        sa.Column('source', sa.String(32), server_default='manual', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('user_domains', 'source')
