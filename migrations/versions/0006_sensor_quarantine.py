"""Bounded rejected payloads with versioned human resolution."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("sensor_quarantine",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sensor_id", sa.String(36), sa.ForeignKey("sensors.id"), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.Column("corrected_event_id", sa.String(36), sa.ForeignKey("sensor_events.id"), nullable=True),
        sa.Column("corrected_payload", sa.JSON(), nullable=True),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.Float(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("sensor_id", "payload_hash", name="uq_quarantine_payload"),
        sa.CheckConstraint("status IN ('pending','replayed','dismissed')", name="ck_quarantine_status"),
        sa.CheckConstraint("version >= 1", name="ck_quarantine_version"),
        sa.CheckConstraint("(status = 'pending' AND corrected_event_id IS NULL AND reviewed_at IS NULL AND reviewer_id IS NULL) OR (status = 'replayed' AND corrected_event_id IS NOT NULL AND reviewed_at IS NOT NULL AND reviewer_id IS NOT NULL) OR (status = 'dismissed' AND corrected_event_id IS NULL AND reviewed_at IS NOT NULL AND reviewer_id IS NOT NULL)", name="ck_quarantine_resolution"),
    )
    op.create_index("ix_sensor_quarantine_sensor_id", "sensor_quarantine", ["sensor_id"])
    op.create_index("ix_sensor_quarantine_status", "sensor_quarantine", ["status"])


def downgrade():
    op.drop_table("sensor_quarantine")
