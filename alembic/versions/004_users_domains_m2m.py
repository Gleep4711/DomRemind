"""add user_domains many-to-many relation

Revision ID: 004
Revises: 002, 003
"""

from alembic import op
import sqlalchemy as sa


revision = '004'
down_revision = ('002', '003')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_domains',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('domain_id', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'domain_id'),
    )

    op.execute(
        """
        INSERT INTO user_domains (user_id, domain_id)
        SELECT user_id, id
        FROM domains
        WHERE user_id IS NOT NULL
        """
    )

    op.drop_column('domains', 'user_id')


def downgrade() -> None:
    op.add_column('domains', sa.Column('user_id', sa.BigInteger(), nullable=True))

    op.execute(
        """
        UPDATE domains d
        SET user_id = ud.user_id
        FROM (
            SELECT domain_id, MIN(user_id) AS user_id
            FROM user_domains
            GROUP BY domain_id
        ) ud
        WHERE d.id = ud.domain_id
        """
    )

    op.drop_table('user_domains')
