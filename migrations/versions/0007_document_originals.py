"""Retained original bytes for new document uploads; no fabricated legacy files."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("document_originals",
        sa.Column("document_id",sa.String(36),sa.ForeignKey("documents.id"),primary_key=True),
        sa.Column("content",sa.LargeBinary(),nullable=False),
        sa.Column("checksum",sa.String(64),nullable=False),
        sa.Column("byte_size",sa.Integer(),nullable=False),
        sa.Column("media_type",sa.String(40),nullable=False),
        sa.Column("archived_at",sa.Float(),nullable=False),
        sa.CheckConstraint("byte_size > 0 AND byte_size <= 10485760",name="ck_original_size"),
        sa.CheckConstraint("media_type IN ('application/pdf','text/plain','text/markdown')",name="ck_original_media"),
        sa.CheckConstraint("length(checksum) = 64",name="ck_original_checksum"),
    )


def downgrade():
    op.drop_table("document_originals")
