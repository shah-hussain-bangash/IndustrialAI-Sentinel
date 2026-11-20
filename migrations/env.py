from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from backend.database import Base, DATABASE_URL

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
target_metadata = Base.metadata


def run_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # Batch recreation of referenced tables needs FK enforcement suspended
            # on this dedicated migration connection, followed by an integrity check.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=DATABASE_URL.startswith("sqlite"),
        )
        try:
            with context.begin_transaction():
                context.run_migrations()
            if sqlite and connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
                raise RuntimeError("Foreign-key integrity failed after migration.")
        finally:
            if sqlite:
                connection.rollback()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
