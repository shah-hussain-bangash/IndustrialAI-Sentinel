"""Expiring hashed account invitation and recovery links."""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('account_links',
        sa.Column('token_hash',sa.String(64),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('purpose',sa.String(10),nullable=False),
        sa.Column('intended_role',sa.String(30),nullable=False),
        sa.Column('account_version',sa.String(64),nullable=False),
        sa.Column('expires',sa.Float(),nullable=False),
        sa.Column('created',sa.Float(),nullable=False),
        sa.Column('state',sa.String(12),nullable=False),
        sa.CheckConstraint("purpose IN ('invite','reset')",name='ck_account_link_purpose'),
        sa.CheckConstraint("state IN ('pending','sent','failed','used','revoked')",name='ck_account_link_state'),
    )
    op.create_index('ix_account_links_user_id','account_links',['user_id'])

def downgrade():
    op.drop_table('account_links')
