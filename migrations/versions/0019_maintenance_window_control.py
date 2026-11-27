"""Exact approved window activation, cancellation and suppressed trigger evidence."""
from alembic import op
import sqlalchemy as sa
revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("maintenance_window_controls",
        sa.Column("draft_id", sa.String(36), sa.ForeignKey("maintenance_window_drafts.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("draft_version", sa.Integer(), nullable=False), sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False), sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["draft_id", "draft_version"], ["maintenance_window_revisions.draft_id", "maintenance_window_revisions.version"]),
        sa.ForeignKeyConstraint(["draft_id", "review_version"], ["maintenance_window_reviews.draft_id", "maintenance_window_reviews.version"]),
        sa.CheckConstraint("(version = 1 AND action = 'activate') OR (version = 2 AND action = 'cancel')", name="ck_window_control_action"))
    op.create_table("maintenance_window_suppressions",
        sa.Column("rule_id", sa.String(36), primary_key=True),
        sa.Column("reading_id", sa.String(36), sa.ForeignKey("readings.id"), primary_key=True),
        sa.Column("rule_version", sa.Integer(), nullable=False), sa.Column("draft_id", sa.String(36), nullable=False),
        sa.Column("control_version", sa.Integer(), nullable=False), sa.Column("observed_at", sa.Float(), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["draft_id", "control_version"], ["maintenance_window_controls.draft_id", "maintenance_window_controls.version"]),
        sa.ForeignKeyConstraint(["rule_id", "rule_version"], ["condition_rule_revisions.rule_id", "condition_rule_revisions.version"]),
        sa.CheckConstraint("control_version = 1", name="ck_window_suppression_activation"))
    op.create_index("ix_maintenance_window_suppressions_draft_id", "maintenance_window_suppressions", ["draft_id"])


def downgrade():
    op.drop_index("ix_maintenance_window_suppressions_draft_id", table_name="maintenance_window_suppressions")
    op.drop_table("maintenance_window_suppressions")
    op.drop_table("maintenance_window_controls")
