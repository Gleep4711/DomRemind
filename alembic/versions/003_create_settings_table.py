"""
create settings table
Revision ID: 003
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('settings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('group', sa.String(), nullable=True),
        sa.Column('param', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('settings')
