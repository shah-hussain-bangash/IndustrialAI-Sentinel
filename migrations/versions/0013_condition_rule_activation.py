"""Controlled exact-revision activation and snapshot-driven condition matches."""
from alembic import op
import sqlalchemy as sa
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("condition_rule_deployments",
        sa.Column("rule_id", sa.String(36), primary_key=True),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("evaluation_version", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.Float(), nullable=False),
        sa.Column("evaluated_at", sa.Float(), nullable=True),
        sa.Column("last_timestamp", sa.Float(), nullable=False),
        sa.Column("candidate_since", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["rule_id", "rule_version"], ["condition_rule_revisions.rule_id", "condition_rule_revisions.version"]),
        sa.CheckConstraint("state IN ('active','paused') AND version >= 1 AND evaluation_version >= 1", name="ck_rule_deployment_state"))
    op.create_table("condition_rule_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(36), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("triggered_at", sa.Float(), nullable=False),
        sa.Column("ended_at", sa.Float(), nullable=True),
        sa.Column("trigger_reading_id", sa.String(36), sa.ForeignKey("readings.id"), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id", "rule_version"], ["condition_rule_revisions.rule_id", "condition_rule_revisions.version"]),
        sa.CheckConstraint("state IN ('active','cleared','data_gap','invalid_sample','paused','replaced')", name="ck_rule_match_state"))
    op.create_index("ix_condition_rule_matches_rule_id", "condition_rule_matches", ["rule_id"])

def downgrade():
    op.drop_table("condition_rule_matches")
    op.drop_table("condition_rule_deployments")
