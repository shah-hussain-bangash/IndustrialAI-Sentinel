"""Append-only application assignment history for condition match reviews."""
from alembic import op
import sqlalchemy as sa
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("condition_rule_assignments",
        sa.Column("match_id", sa.String(36), sa.ForeignKey("condition_rule_matches.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("owner_name", sa.String(200), nullable=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_rule_assignment_version"),
        sa.CheckConstraint("(owner_id IS NULL AND owner_name IS NULL) OR (owner_id IS NOT NULL AND owner_name IS NOT NULL)", name="ck_rule_assignment_owner"))


def downgrade():
    op.drop_table("condition_rule_assignments")
