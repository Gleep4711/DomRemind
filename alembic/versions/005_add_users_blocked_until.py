"""add users blocked_until column

Revision ID: 005
Revises: 004
"""

from alembic import op
import sqlalchemy as sa


revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('blocked_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'blocked_until')
