"""
create domains table
Revision ID: 002
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('domains',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('domain', sa.String(), nullable=True),
        sa.Column('expired_date', sa.DateTime(), nullable=True),
        sa.Column('last_check', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_domains'))
    )

def downgrade() -> None:
    op.drop_table('domains')
