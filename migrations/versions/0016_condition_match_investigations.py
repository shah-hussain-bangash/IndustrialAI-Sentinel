"""One traceable investigation per condition rule match."""
from alembic import op
import sqlalchemy as sa
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("condition_match_investigations",
        sa.Column("match_id", sa.String(36), sa.ForeignKey("condition_rule_matches.id"), primary_key=True),
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False, unique=True),
        sa.Column("created", sa.Float(), nullable=False))


def downgrade():
    op.drop_table("condition_match_investigations")
