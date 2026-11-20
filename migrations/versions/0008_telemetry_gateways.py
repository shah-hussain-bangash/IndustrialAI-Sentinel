"""Asset-scoped hashed sender credentials and revocation state."""
from alembic import op
import sqlalchemy as sa

revision="0008"
down_revision="0007"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table("telemetry_gateways",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("asset_id",sa.String(36),sa.ForeignKey("assets.id"),nullable=False),
        sa.Column("issuer_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("name",sa.String(100),nullable=False),
        sa.Column("token_hash",sa.String(64),nullable=False,unique=True),
        sa.Column("status",sa.String(20),nullable=False),
        sa.Column("version",sa.Integer(),nullable=False),
        sa.Column("created",sa.Float(),nullable=False),
        sa.Column("expires",sa.Float(),nullable=False),
        sa.Column("last_used",sa.Float(),nullable=True),
        sa.Column("accepted_batches",sa.Integer(),nullable=False),
        sa.Column("revoked_at",sa.Float(),nullable=True),
        sa.CheckConstraint("status IN ('active','revoked')",name="ck_gateway_status"),
        sa.CheckConstraint("version >= 1 AND accepted_batches >= 0",name="ck_gateway_counters"),
        sa.CheckConstraint("expires > created",name="ck_gateway_expiry"),
        sa.CheckConstraint("(status = 'active' AND revoked_at IS NULL) OR (status = 'revoked' AND revoked_at IS NOT NULL)",name="ck_gateway_revocation"),
    )
    op.create_index("ix_telemetry_gateways_asset_id","telemetry_gateways",["asset_id"])


def downgrade():
    op.drop_table("telemetry_gateways")
