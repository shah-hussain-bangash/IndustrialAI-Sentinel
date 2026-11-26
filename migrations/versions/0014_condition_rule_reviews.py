"""Append-only application review history for condition rule matches."""
from alembic import op
import sqlalchemy as sa
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("condition_rule_reviews",
        sa.Column("match_id", sa.String(36), sa.ForeignKey("condition_rule_matches.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.CheckConstraint("version >= 1 AND state IN ('acknowledged','resolved')", name="ck_rule_review_state"))

def downgrade():
    op.drop_table("condition_rule_reviews")
