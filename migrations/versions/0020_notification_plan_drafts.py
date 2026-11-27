"""Inactive exact-rule notification plans and immutable revision history."""
from alembic import op
import sqlalchemy as sa
revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("notification_plan_revisions",
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("condition_rules.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False), sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id", "rule_version"], ["condition_rule_revisions.rule_id", "condition_rule_revisions.version"]),
        sa.CheckConstraint("version >= 1 AND rule_version >= 1", name="ck_notification_plan_version"))


def downgrade():
    op.drop_table("notification_plan_revisions")
