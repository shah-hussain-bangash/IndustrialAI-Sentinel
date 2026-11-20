"""Traceable projection of time-aligned events into complete snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("snapshot_projections",
        sa.Column("reading_id", sa.String(36), sa.ForeignKey("readings.id"), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("frame_hash", sa.String(64), nullable=False, unique=True),
        *[sa.Column(channel+"_event_id", sa.String(36), sa.ForeignKey("sensor_events.id"), nullable=False) for channel in ("vibration", "temperature", "pressure", "flow")],
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.Column("policy", sa.String(40), nullable=False),
    )
    op.create_index("ix_snapshot_projections_asset_id", "snapshot_projections", ["asset_id"])


def downgrade():
    op.drop_table("snapshot_projections")
