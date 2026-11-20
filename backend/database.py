"""SQLAlchemy persistence. SQLite makes the local demo work without services."""

import os
import time
import uuid
from pathlib import Path
from sqlalchemy import (
    create_engine,
    event,
    String,
    Text,
    Float,
    LargeBinary,
    Integer,
    JSON,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("SENTINEL_DATA_DIR", str(ROOT / "data")))
DATA.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f'sqlite:///{(DATA / "sentinel.db").as_posix()}')
engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False, "timeout": 20} if DATABASE_URL.startswith("sqlite") else {}
    ),
    pool_pre_ping=True,
)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_options(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def uid():
    return str(uuid.uuid4())


def now():
    return time.time()


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (
        UniqueConstraint("id", "name", name="uq_site_id_name"),
        CheckConstraint("length(trim(name)) > 0", name="ck_site_name"),
        CheckConstraint("version >= 1", name="ck_site_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Dubai")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[float] = mapped_column(Float, default=now)


class Organization(Base):
    """Single-company profile. This is deliberately not multi-tenant isolation."""
    __tablename__ = "organization"
    __table_args__ = (
        CheckConstraint("id = 'primary'", name="ck_organization_singleton"),
        CheckConstraint("length(trim(name)) > 0", name="ck_organization_name"),
        CheckConstraint("version >= 1 AND configured IN (0,1)", name="ck_organization_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="primary")
    name: Mapped[str] = mapped_column(String(160), default="Your organization")
    description: Mapped[str] = mapped_column(String(500), default="")
    configured: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[float] = mapped_column(Float, default=now)


class SiteArea(Base):
    __tablename__ = "site_areas"
    __table_args__ = (
        UniqueConstraint("site_id", "code", name="uq_area_site_code"),
        UniqueConstraint("id", "site_id", name="uq_area_site_identity"),
        CheckConstraint("length(trim(name)) > 0 AND length(trim(code)) > 0", name="ck_area_labels"),
        CheckConstraint("version >= 1", name="ck_area_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[float] = mapped_column(Float, default=now)


class EquipmentSystem(Base):
    __tablename__ = "equipment_systems"
    __table_args__ = (
        ForeignKeyConstraint(["area_id", "site_id"], ["site_areas.id", "site_areas.site_id"], name="fk_system_area_site"),
        UniqueConstraint("area_id", "code", name="uq_system_area_code"),
        UniqueConstraint("id", "site_id", name="uq_system_site_identity"),
        CheckConstraint("length(trim(name)) > 0 AND length(trim(code)) > 0", name="ck_system_labels"),
        CheckConstraint("version >= 1", name="ck_system_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    area_id: Mapped[str] = mapped_column(String(36), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[float] = mapped_column(Float, default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(Text)
    sites: Mapped[list] = mapped_column(JSON, default=list)


class SiteMembership(Base):
    __tablename__ = "site_memberships"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), primary_key=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    csrf: Mapped[str] = mapped_column(String(100))
    expires: Mapped[float] = mapped_column(Float)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("site", "tag"), UniqueConstraint("id", "site_id", name="uq_asset_site_identity"), ForeignKeyConstraint(["site_id", "site"], ["sites.id", "sites.name"], name="fk_asset_site_identity"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tag: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(50))
    site: Mapped[str] = mapped_column(String(100), index=True)
    site_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(100))
    criticality: Mapped[str] = mapped_column(String(30), default="High")
    manufacturer: Mapped[str] = mapped_column(String(100), default="Demonstration equipment")
    installed: Mapped[str] = mapped_column(String(20), default="2023-06-01")
    version: Mapped[int] = mapped_column(Integer, default=1)
    threshold: Mapped[float] = mapped_column(Float, default=4.5)


class EquipmentPlacement(Base):
    __tablename__ = "equipment_placements"
    __table_args__ = (
        ForeignKeyConstraint(["asset_id", "site_id"], ["assets.id", "assets.site_id"], name="fk_placement_asset_site"),
        ForeignKeyConstraint(["system_id", "site_id"], ["equipment_systems.id", "equipment_systems.site_id"], name="fk_placement_system_site"),
        CheckConstraint("version >= 1", name="ck_placement_version"),
    )
    asset_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    system_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Sensor(Base):
    __tablename__ = "sensors"
    __table_args__ = (
        UniqueConstraint("asset_id", "channel", name="uq_sensor_asset_channel"),
        CheckConstraint("(channel = 'vibration' AND unit = 'mm/s') OR (channel = 'temperature' AND unit = 'degC') OR (channel = 'pressure' AND unit = 'bar') OR (channel = 'flow' AND unit = 'm3/h')", name="ck_sensor_channel_unit"),
        CheckConstraint("expected_interval_seconds >= 1 AND expected_interval_seconds <= 86400", name="ck_sensor_interval"),
        CheckConstraint("stale_after_seconds >= expected_interval_seconds AND stale_after_seconds <= 604800", name="ck_sensor_freshness"),
        CheckConstraint("version >= 1", name="ck_sensor_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    unit: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(100))
    expected_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    stale_after_seconds: Mapped[int] = mapped_column(Integer, default=900)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[float] = mapped_column(Float, default=now)


class SensorEvent(Base):
    __tablename__ = "sensor_events"
    __table_args__ = (
        UniqueConstraint("sensor_id", "message_id", name="uq_event_sensor_message"),
        CheckConstraint("quality IN ('good','suspect','bad')", name="ck_event_quality"),
        CheckConstraint("observed_at > 0", name="ck_event_time"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    sensor_id: Mapped[str] = mapped_column(ForeignKey("sensors.id"), index=True)
    message_id: Mapped[str] = mapped_column(String(100))
    observed_at: Mapped[float] = mapped_column(Float, index=True)
    received_at: Mapped[float] = mapped_column(Float, default=now)
    raw_value: Mapped[float] = mapped_column(Float)
    raw_unit: Mapped[str] = mapped_column(String(20))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    quality: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(80))
    conversion: Mapped[str] = mapped_column(String(30), default="units-v1")


class TelemetryGateway(Base):
    __tablename__ = "telemetry_gateways"
    __table_args__ = (
        CheckConstraint("status IN ('active','revoked')",name="ck_gateway_status"),
        CheckConstraint("version >= 1 AND accepted_batches >= 0",name="ck_gateway_counters"),
        CheckConstraint("expires > created",name="ck_gateway_expiry"),
        CheckConstraint("(status = 'active' AND revoked_at IS NULL) OR (status = 'revoked' AND revoked_at IS NOT NULL)",name="ck_gateway_revocation"),
    )
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"),index=True)
    issuer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64),unique=True)
    status: Mapped[str] = mapped_column(String(20),default="active")
    version: Mapped[int] = mapped_column(Integer,default=1)
    created: Mapped[float] = mapped_column(Float,default=now)
    expires: Mapped[float] = mapped_column(Float)
    last_used: Mapped[float | None] = mapped_column(Float,nullable=True)
    accepted_batches: Mapped[int] = mapped_column(Integer,default=0)
    revoked_at: Mapped[float | None] = mapped_column(Float,nullable=True)


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    timestamp: Mapped[float] = mapped_column(Float, index=True)
    vibration: Mapped[float] = mapped_column(Float)
    temperature: Mapped[float] = mapped_column(Float)
    pressure: Mapped[float] = mapped_column(Float)
    flow: Mapped[float] = mapped_column(Float)
    quality: Mapped[str] = mapped_column(String(20), default="good")
    message_id: Mapped[str] = mapped_column(String(100), unique=True, default=uid)


class SnapshotProjection(Base):
    __tablename__ = "snapshot_projections"
    reading_id: Mapped[str] = mapped_column(ForeignKey("readings.id"), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    frame_hash: Mapped[str] = mapped_column(String(64), unique=True)
    vibration_event_id: Mapped[str] = mapped_column(ForeignKey("sensor_events.id"))
    temperature_event_id: Mapped[str] = mapped_column(ForeignKey("sensor_events.id"))
    pressure_event_id: Mapped[str] = mapped_column(ForeignKey("sensor_events.id"))
    flow_event_id: Mapped[str] = mapped_column(ForeignKey("sensor_events.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created: Mapped[float] = mapped_column(Float, default=now)
    policy: Mapped[str] = mapped_column(String(40), default="aligned-events-v1")


class SensorQuarantine(Base):
    __tablename__ = "sensor_quarantine"
    __table_args__ = (
        UniqueConstraint("sensor_id", "payload_hash", name="uq_quarantine_payload"),
        CheckConstraint("status IN ('pending','replayed','dismissed')", name="ck_quarantine_status"),
        CheckConstraint("version >= 1", name="ck_quarantine_version"),
        CheckConstraint("(status = 'pending' AND corrected_event_id IS NULL AND reviewed_at IS NULL AND reviewer_id IS NULL) OR (status = 'replayed' AND corrected_event_id IS NOT NULL AND reviewed_at IS NOT NULL AND reviewer_id IS NOT NULL) OR (status = 'dismissed' AND corrected_event_id IS NULL AND reviewed_at IS NOT NULL AND reviewer_id IS NOT NULL)", name="ck_quarantine_resolution"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    sensor_id: Mapped[str] = mapped_column(ForeignKey("sensors.id"), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[dict] = mapped_column(JSON)
    validation_errors: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    submitted_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created: Mapped[float] = mapped_column(Float, default=now)
    corrected_event_id: Mapped[str | None] = mapped_column(ForeignKey("sensor_events.id"), nullable=True)
    corrected_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Episode(Base):
    __tablename__ = "episodes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(30), default="active")
    created: Mapped[float] = mapped_column(Float, default=now)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (ForeignKeyConstraint(["site_id", "site"], ["sites.id", "sites.name"], name="fk_document_site_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(240))
    site: Mapped[str] = mapped_column(String(100), index=True)
    site_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), default="All equipment")
    version: Mapped[str] = mapped_column(String(40), default="1.0")
    pages: Mapped[list] = mapped_column(JSON, default=list)
    checksum: Mapped[str] = mapped_column(String(64))
    created: Mapped[float] = mapped_column(Float, default=now)


class DocumentOriginal(Base):
    __tablename__ = "document_originals"
    __table_args__ = (
        CheckConstraint("byte_size > 0 AND byte_size <= 10485760", name="ck_original_size"),
        CheckConstraint("media_type IN ('application/pdf','text/plain','text/markdown')", name="ck_original_media"),
        CheckConstraint("length(checksum) = 64", name="ck_original_checksum"),
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    checksum: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(40))
    archived_at: Mapped[float] = mapped_column(Float, default=now)


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(240))
    state: Mapped[str] = mapped_column(String(40), default="awaiting_review")
    created: Mapped[float] = mapped_column(Float, default=now)
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_until: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_reason: Mapped[str] = mapped_column(Text, default="")


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reference: Mapped[str] = mapped_column(String(80), unique=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), unique=True)
    title: Mapped[str] = mapped_column(String(240))
    priority: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40), default="planned")
    assignee: Mapped[str] = mapped_column(String(100), default="Unassigned")
    due_date: Mapped[str] = mapped_column(String(30))
    external_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    version: Mapped[int] = mapped_column(Integer, default=1)
    outcome: Mapped[str] = mapped_column(Text, default="")


class RecommendationRevision(Base):
    __tablename__ = "recommendation_revisions"
    __table_args__ = (UniqueConstraint("investigation_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    created: Mapped[float] = mapped_column(Float, default=now)


class ExternalOrder(Base):
    """Local, persistent CMMS simulator. No vendor connection is implied."""

    __tablename__ = "simulated_cmms"
    command_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_ref: Mapped[str] = mapped_column(String(80), unique=True)
    state: Mapped[str] = mapped_column(String(20), default="accepted")


class Audit(Base):
    __tablename__ = "audit_events"
    __table_args__ = (ForeignKeyConstraint(["site_id", "site"], ["sites.id", "sites.name"], name="fk_audit_site_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site: Mapped[str] = mapped_column(String(100), index=True)
    site_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(120))
    target: Mapped[str] = mapped_column(String(240))
    details: Mapped[str] = mapped_column(Text, default="")
    created: Mapped[float] = mapped_column(Float, default=now)


class Idempotency(Base):
    __tablename__ = "idempotency"
    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    created: Mapped[float] = mapped_column(Float, default=now)


class Preference(Base):
    __tablename__ = "preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)


# Compatibility bridge: legacy site-name constructors resolve a canonical identity.
# Direct SQL writes remain protected by the composite foreign keys.
def stable_site_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "industrialai-sentinel/site/" + name))


def _ensure_site(connection, name):
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as postgres_insert
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError("Invalid site name.")
    insert = sqlite_insert if connection.dialect.name == "sqlite" else postgres_insert
    connection.execute(insert(Site).values(id=stable_site_id(name), name=name, display_name=name, timezone="Asia/Dubai", version=1, created=now()).on_conflict_do_nothing(index_elements=["name"]))
    from sqlalchemy import select
    return connection.scalar(select(Site.id).where(Site.name == name))


def _sync_memberships(connection, user):
    from sqlalchemy import delete, insert
    ids = {_ensure_site(connection, name) for name in user.sites}
    connection.execute(delete(SiteMembership).where(SiteMembership.user_id == user.id))
    if ids:
        connection.execute(insert(SiteMembership), [{"user_id":user.id, "site_id":id} for id in sorted(ids)])


@event.listens_for(User, "after_insert")
def _membership_insert(mapper, connection, target):
    _sync_memberships(connection, target)


@event.listens_for(User, "after_update")
def _membership_update(mapper, connection, target):
    from sqlalchemy import inspect
    if inspect(target).attrs.sites.history.has_changes():
        _sync_memberships(connection, target)


def _site_reference(mapper, connection, target):
    if not target.site_id:
        target.site_id = _ensure_site(connection, target.site)


for _site_model in (Asset, Document, Audit):
    event.listen(_site_model, "before_insert", _site_reference)
