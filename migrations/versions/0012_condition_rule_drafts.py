"""Inactive condition rule drafts and immutable application revision history."""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("condition_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_condition_rule_version"))
    op.create_index("ix_condition_rules_asset_id", "condition_rules", ["asset_id"])
    op.create_table("condition_rule_revisions",
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("condition_rules.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_condition_rule_revision_version"))


def downgrade():
    op.drop_table("condition_rule_revisions")
    op.drop_table("condition_rules")
