"""Independent sensor events with original units and duplicate protection."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("sensor_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sensor_id", sa.String(36), sa.ForeignKey("sensors.id"), nullable=False),
        sa.Column("message_id", sa.String(100), nullable=False),
        sa.Column("observed_at", sa.Float(), nullable=False),
        sa.Column("received_at", sa.Float(), nullable=False),
        sa.Column("raw_value", sa.Float(), nullable=False),
        sa.Column("raw_unit", sa.String(20), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("quality", sa.String(20), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("conversion", sa.String(30), nullable=False),
        sa.UniqueConstraint("sensor_id", "message_id", name="uq_event_sensor_message"),
        sa.CheckConstraint("quality IN ('good','suspect','bad')", name="ck_event_quality"),
        sa.CheckConstraint("observed_at > 0", name="ck_event_time"),
    )
    op.create_index("ix_sensor_events_sensor_id", "sensor_events", ["sensor_id"])
    op.create_index("ix_sensor_events_observed_at", "sensor_events", ["observed_at"])


def downgrade():
    op.drop_table("sensor_events")
