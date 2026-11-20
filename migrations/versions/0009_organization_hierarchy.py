"""Single-company profile and site-scoped equipment hierarchy."""
import time
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    organization = op.create_table("organization",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("name",sa.String(160),nullable=False),
        sa.Column("description",sa.String(500),nullable=False),
        sa.Column("configured",sa.Integer(),nullable=False),
        sa.Column("version",sa.Integer(),nullable=False),
        sa.Column("created",sa.Float(),nullable=False),
        sa.CheckConstraint("id = 'primary'",name="ck_organization_singleton"),
        sa.CheckConstraint("length(trim(name)) > 0",name="ck_organization_name"),
        sa.CheckConstraint("version >= 1 AND configured IN (0,1)",name="ck_organization_version"),
    )
    op.bulk_insert(organization,[dict(id="primary",name="Your organization",description="",configured=0,version=1,created=time.time())])
    with op.batch_alter_table("assets") as batch:
        batch.create_unique_constraint("uq_asset_site_identity",["id","site_id"])
    op.create_table("site_areas",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("site_id",sa.String(36),sa.ForeignKey("sites.id"),nullable=False),
        sa.Column("code",sa.String(30),nullable=False),
        sa.Column("name",sa.String(120),nullable=False),
        sa.Column("version",sa.Integer(),nullable=False),
        sa.Column("created",sa.Float(),nullable=False),
        sa.UniqueConstraint("site_id","code",name="uq_area_site_code"),
        sa.UniqueConstraint("id","site_id",name="uq_area_site_identity"),
        sa.CheckConstraint("length(trim(name)) > 0 AND length(trim(code)) > 0",name="ck_area_labels"),
        sa.CheckConstraint("version >= 1",name="ck_area_version"),
    )
    op.create_index("ix_site_areas_site_id","site_areas",["site_id"])
    op.create_table("equipment_systems",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("site_id",sa.String(36),sa.ForeignKey("sites.id"),nullable=False),
        sa.Column("area_id",sa.String(36),nullable=False),
        sa.Column("code",sa.String(30),nullable=False),
        sa.Column("name",sa.String(120),nullable=False),
        sa.Column("version",sa.Integer(),nullable=False),
        sa.Column("created",sa.Float(),nullable=False),
        sa.ForeignKeyConstraint(["area_id","site_id"],["site_areas.id","site_areas.site_id"],name="fk_system_area_site"),
        sa.UniqueConstraint("area_id","code",name="uq_system_area_code"),
        sa.UniqueConstraint("id","site_id",name="uq_system_site_identity"),
        sa.CheckConstraint("length(trim(name)) > 0 AND length(trim(code)) > 0",name="ck_system_labels"),
        sa.CheckConstraint("version >= 1",name="ck_system_version"),
    )
    op.create_index("ix_equipment_systems_site_id","equipment_systems",["site_id"])
    op.create_index("ix_equipment_systems_area_id","equipment_systems",["area_id"])
    op.create_table("equipment_placements",
        sa.Column("asset_id",sa.String(36),primary_key=True),
        sa.Column("site_id",sa.String(36),sa.ForeignKey("sites.id"),nullable=False),
        sa.Column("system_id",sa.String(36),nullable=True),
        sa.Column("version",sa.Integer(),nullable=False),
        sa.ForeignKeyConstraint(["asset_id","site_id"],["assets.id","assets.site_id"],name="fk_placement_asset_site"),
        sa.ForeignKeyConstraint(["system_id","site_id"],["equipment_systems.id","equipment_systems.site_id"],name="fk_placement_system_site"),
        sa.CheckConstraint("version >= 1",name="ck_placement_version"),
    )
    op.create_index("ix_equipment_placements_site_id","equipment_placements",["site_id"])
    op.create_index("ix_equipment_placements_system_id","equipment_placements",["system_id"])


def downgrade():
    op.drop_table("equipment_placements")
    op.drop_table("equipment_systems")
    op.drop_table("site_areas")
    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("uq_asset_site_identity",type_="unique")
    op.drop_table("organization")
