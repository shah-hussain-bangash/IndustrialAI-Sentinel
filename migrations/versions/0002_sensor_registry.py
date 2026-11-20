"""Add stable sensor registry identities without changing existing readings.

Revision ID: 0002
Revises: 0001
"""

import time
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    sensors = op.create_table(
        "sensors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("expected_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("stale_after_seconds", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.UniqueConstraint("asset_id", "channel", name="uq_sensor_asset_channel"),
        sa.CheckConstraint("(channel = 'vibration' AND unit = 'mm/s') OR (channel = 'temperature' AND unit = 'degC') OR (channel = 'pressure' AND unit = 'bar') OR (channel = 'flow' AND unit = 'm3/h')", name="ck_sensor_channel_unit"),
        sa.CheckConstraint("expected_interval_seconds >= 1 AND expected_interval_seconds <= 86400", name="ck_sensor_interval"),
        sa.CheckConstraint("stale_after_seconds >= expected_interval_seconds AND stale_after_seconds <= 604800", name="ck_sensor_freshness"),
        sa.CheckConstraint("version >= 1", name="ck_sensor_version"),
    )
    op.create_index("ix_sensors_asset_id", "sensors", ["asset_id"])
    bind = op.get_bind()
    for asset_id in bind.execute(sa.text("SELECT id FROM assets")).scalars():
        for channel, unit in {"vibration":"mm/s", "temperature":"degC", "pressure":"bar", "flow":"m3/h"}.items():
            bind.execute(sensors.insert().values(id=str(uuid.uuid5(uuid.NAMESPACE_URL,f"industrialai-sentinel/sensor/{asset_id}/{channel}")), asset_id=asset_id, channel=channel, unit=unit, label=channel.title(), expected_interval_seconds=300, stale_after_seconds=900, version=1, created=time.time()))


def downgrade():
    op.drop_index("ix_sensors_asset_id", table_name="sensors")
    op.drop_table("sensors")
