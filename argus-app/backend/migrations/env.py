import os

from alembic import context

from backend.database import Base, create_engine_from_url

config = context.config


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=os.environ["ARGUS_DATABASE_URL"], target_metadata=Base.metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    engine = create_engine_from_url(os.environ["ARGUS_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            migrate(connection)
    finally:
        engine.dispose()
