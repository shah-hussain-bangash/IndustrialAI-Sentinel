"""Independent planning decisions bound to exact notification-plan revisions."""
from alembic import op
import sqlalchemy as sa
revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("notification_plan_reviews",
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("condition_rules.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True), sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False), sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id", "plan_version"], ["notification_plan_revisions.rule_id", "notification_plan_revisions.version"]),
        sa.CheckConstraint("version >= 1 AND plan_version >= 1 AND state IN ('approved','rejected')", name="ck_notification_review_state"))


def downgrade():
    op.drop_table("notification_plan_reviews")
