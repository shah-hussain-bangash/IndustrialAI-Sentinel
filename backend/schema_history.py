"""Reflect immutable older revisions in memory for checked legacy adoption."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, create_engine


def historical_metadata(revision):
    root=Path(__file__).resolve().parents[1]/"migrations"/"versions"
    memory=create_engine("sqlite://")
    metadata=MetaData()
    try:
        with memory.connect() as connection:
            for name in ("0001_initial_reference_application_schema.py","0002_sensor_registry.py","0003_site_identities.py","0004_sensor_events.py","0005_snapshot_projections.py","0006_sensor_quarantine.py","0007_document_originals.py"):
                spec=importlib.util.spec_from_file_location("historical_"+name[:4],root/name)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                with Operations.context(MigrationContext.configure(connection)):
                    module.upgrade()
                if name.startswith(revision):break
            metadata.reflect(connection)
        return metadata
    finally:memory.dispose()
