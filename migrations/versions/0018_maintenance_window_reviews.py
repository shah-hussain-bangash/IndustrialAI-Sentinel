"""Independent planning review of an exact maintenance-window revision."""
from alembic import op
import sqlalchemy as sa
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("maintenance_window_reviews",
        sa.Column("draft_id", sa.String(36), sa.ForeignKey("maintenance_window_drafts.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["draft_id", "draft_version"], ["maintenance_window_revisions.draft_id", "maintenance_window_revisions.version"]),
        sa.CheckConstraint("version >= 1 AND draft_version >= 1 AND state IN ('approved', 'rejected')", name="ck_window_review_state"))


def downgrade():
    op.drop_table("maintenance_window_reviews")
