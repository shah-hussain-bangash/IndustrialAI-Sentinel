"""Canonical site identities, memberships and checked legacy-name bridges.

Revision ID: 0003
Revises: 0002
"""

import json
import time
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    users = list(bind.execute(sa.text("SELECT id, sites FROM users")))
    memberships = {}
    names = set()
    for id, sites in users:
        sites = json.loads(sites) if isinstance(sites, str) else sites
        if not isinstance(sites, list) or any(not isinstance(s, str) for s in sites):
            raise RuntimeError("Invalid legacy site membership data; migration stopped.")
        memberships[id] = set(sites)
        names.update(sites)
    for table in ("assets", "documents", "audit_events"):
        names.update(bind.execute(sa.text(f"SELECT DISTINCT site FROM {table}")).scalars())
    if any(not isinstance(s, str) or not s.strip() or len(s)>100 for s in names):
        raise RuntimeError("Invalid legacy site names; migration stopped.")
    sites = op.create_table("sites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.UniqueConstraint("id", "name", name="uq_site_id_name"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_site_name"),
        sa.CheckConstraint("version >= 1", name="ck_site_version"),
    )
    mapping = {name:str(uuid.uuid5(uuid.NAMESPACE_URL,"industrialai-sentinel/site/"+name)) for name in names}
    for name, id in mapping.items():
        bind.execute(sites.insert().values(id=id,name=name,display_name=name,timezone="Asia/Dubai",version=1,created=time.time()))
    member_table = op.create_table("site_memberships",
        sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),primary_key=True),
        sa.Column("site_id",sa.String(36),sa.ForeignKey("sites.id"),primary_key=True),
    )
    for user_id, user_names in memberships.items():
        for name in user_names:
            bind.execute(member_table.insert().values(user_id=user_id,site_id=mapping[name]))
    for table, prefix in (("assets","asset"),("documents","document"),("audit_events","audit")):
        op.add_column(table, sa.Column("site_id",sa.String(36),nullable=True))
        for name,id in mapping.items():
            bind.execute(sa.text(f"UPDATE {table} SET site_id = :site_id WHERE site = :name"),{"site_id":id,"name":name})
        with op.batch_alter_table(table) as batch:
            batch.alter_column("site_id",existing_type=sa.String(36),nullable=False)
            batch.create_foreign_key(f"fk_{prefix}_site_identity","sites",["site_id","site"],["id","name"])
            batch.create_index(f"ix_{table}_site_id",["site_id"])


def downgrade():
    for table,prefix in (("assets","asset"),("documents","document"),("audit_events","audit")):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{prefix}_site_identity",type_="foreignkey")
            batch.drop_index(f"ix_{table}_site_id")
            batch.drop_column("site_id")
    op.drop_table("site_memberships")
    op.drop_table("sites")
