"""Encrypted authenticator enrollment, backup codes and administrator MFA policy."""
from alembic import op
import sqlalchemy as sa
revision='0011'
down_revision='0010'
branch_labels=None
depends_on=None
def upgrade():
    with op.batch_alter_table('login_sessions') as batch:
        batch.add_column(sa.Column('mfa_verified',sa.Integer(),nullable=False,server_default='0'))
    op.create_table('mfa_credentials',
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('secret_encrypted',sa.Text(),nullable=False),
        sa.Column('enabled',sa.Integer(),nullable=False),
        sa.Column('enrollment_expires',sa.Float(),nullable=False),
        sa.Column('last_step',sa.Integer(),nullable=False),
        sa.Column('recovery_hashes',sa.JSON(),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.CheckConstraint('enabled IN (0,1) AND version >= 1',name='ck_mfa_credential_state'))
    op.create_table('mfa_challenges',
        sa.Column('token_hash',sa.String(64),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('csrf',sa.String(64),nullable=False),
        sa.Column('account_version',sa.String(64),nullable=False),
        sa.Column('expires',sa.Float(),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False))
    op.create_index('ix_mfa_challenges_user_id','mfa_challenges',['user_id'])
    policy=op.create_table('mfa_policy',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('required',sa.Integer(),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.CheckConstraint("id = 'primary' AND required IN (0,1) AND version >= 1",name='ck_mfa_policy_state'))
    op.bulk_insert(policy,[dict(id='primary',required=0,version=1)])
def downgrade():
    op.drop_table('mfa_challenges');op.drop_table('mfa_credentials');op.drop_table('mfa_policy')
    with op.batch_alter_table('login_sessions') as batch:batch.drop_column('mfa_verified')
