"""Local-only notification rehearsal queue and simulated attempt history."""
from alembic import op
import sqlalchemy as sa
revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("notification_rehearsals",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("rule_id",sa.String(36),sa.ForeignKey("condition_rules.id"),nullable=False),
        sa.Column("plan_version",sa.Integer(),nullable=False),sa.Column("review_version",sa.Integer(),nullable=False),
        sa.Column("match_id",sa.String(36),sa.ForeignKey("condition_rule_matches.id"),nullable=False),
        sa.Column("recipients",sa.JSON(),nullable=False),sa.Column("version",sa.Integer(),nullable=False),
        sa.Column("state",sa.String(30),nullable=False),sa.Column("attempts",sa.Integer(),nullable=False),sa.Column("next_attempt_at",sa.Float(),nullable=True),
        sa.Column("actor_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("actor_name",sa.String(200),nullable=False),
        sa.Column("reason",sa.String(1000),nullable=False),sa.Column("created",sa.Float(),nullable=False),
        sa.ForeignKeyConstraint(["rule_id","plan_version"],["notification_plan_revisions.rule_id","notification_plan_revisions.version"]),
        sa.ForeignKeyConstraint(["rule_id","review_version"],["notification_plan_reviews.rule_id","notification_plan_reviews.version"]),
        sa.UniqueConstraint("rule_id","review_version","match_id",name="uq_notification_rehearsal_source"),
        sa.CheckConstraint("version >= 1 AND attempts >= 0 AND attempts <= 3",name="ck_rehearsal_version"),
        sa.CheckConstraint("(state IN ('queued','retry_wait') AND next_attempt_at IS NOT NULL) OR (state IN ('simulated_success','simulated_failure','exhausted','cancelled','blocked') AND next_attempt_at IS NULL)",name="ck_rehearsal_state"))
    op.create_index("ix_notification_rehearsals_rule_id","notification_rehearsals",["rule_id"])
    op.create_table("notification_rehearsal_events",
        sa.Column("rehearsal_id",sa.String(36),sa.ForeignKey("notification_rehearsals.id"),primary_key=True),sa.Column("version",sa.Integer(),primary_key=True),
        sa.Column("action",sa.String(40),nullable=False),sa.Column("attempt_number",sa.Integer(),nullable=False),sa.Column("check_reasons",sa.JSON(),nullable=False),
        sa.Column("actor_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("actor_name",sa.String(200),nullable=False),
        sa.Column("reason",sa.String(1000),nullable=False),sa.Column("created",sa.Float(),nullable=False),
        sa.CheckConstraint("version >= 1 AND attempt_number >= 0 AND attempt_number <= 3",name="ck_rehearsal_event_version"),
        sa.CheckConstraint("action IN ('enqueue','simulate_success','simulate_retryable_failure','simulate_permanent_failure','cancel','block')",name="ck_rehearsal_event_action"))


def downgrade():
    op.drop_table("notification_rehearsal_events")
    op.drop_index("ix_notification_rehearsals_rule_id",table_name="notification_rehearsals")
    op.drop_table("notification_rehearsals")
