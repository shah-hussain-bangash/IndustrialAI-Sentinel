"""Inactive maintenance-window plans and immutable revision history."""
from alembic import op
import sqlalchemy as sa
revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("maintenance_window_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("created", sa.Float(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_window_draft_version"))
    op.create_index("ix_maintenance_window_drafts_asset_id", "maintenance_window_drafts", ["asset_id"])
    op.create_table("maintenance_window_revisions",
        sa.Column("draft_id", sa.String(36), sa.ForeignKey("maintenance_window_drafts.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("starts_at", sa.Float(), nullable=False), sa.Column("ends_at", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False), sa.Column("created", sa.Float(), nullable=False),
        sa.CheckConstraint("version >= 1 AND starts_at >= 0 AND ends_at > starts_at AND ends_at - starts_at <= 604800", name="ck_window_revision_range"))


def downgrade():
    op.drop_table("maintenance_window_revisions")
    op.drop_index("ix_maintenance_window_drafts_asset_id", table_name="maintenance_window_drafts")
    op.drop_table("maintenance_window_drafts")
