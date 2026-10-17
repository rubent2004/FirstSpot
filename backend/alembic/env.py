"""Alembic async migration environment configured with GeoAlchemy2 helpers."""

import asyncio
from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.core.database import Base
from app.modules.places.infrastructure.models import VulnerablePlaceModel  # noqa: F401
from app.modules.places.infrastructure.models import PlaceActivityModel  # noqa: F401
from app.modules.institutions.infrastructure.models import (  # noqa: F401
    InstitutionInviteModel,
    InstitutionModel,
    InstitutionUserModel,
)
from app.modules.census.infrastructure.models import (  # noqa: F401
    CensusAdminUnitModel,
    CensusIndicatorModel,
    CensusPopulationUnitModel,
    CensusSegmentModel,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

# Schemas owned by PostGIS extensions rather than by this project.
EXTENSION_SCHEMAS = frozenset({"tiger", "tiger_data", "topology"})


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    """Keep autogenerate from touching objects this project does not own.

    The PostGIS TIGER geocoder and topology extensions create dozens of tables
    that are reflected from the database but absent from ``Base.metadata``.
    Without this filter, ``alembic revision --autogenerate`` emits DROP
    statements for every one of them, which would uninstall the extensions.

    Anything reflected from the database that our metadata does not declare is
    therefore skipped, along with any index or constraint hanging off it.
    """
    if getattr(object_, "schema", None) in EXTENSION_SCHEMAS:
        return False

    if reflected:
        if type_ == "table" and name not in target_metadata.tables:
            return False
        parent = getattr(object_, "table", None)
        if parent is not None and parent.name not in target_metadata.tables:
            return False

    return alembic_helpers.include_object(object_, name, type_, reflected, compare_to)


def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic context with GeoAlchemy2 support and run migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async Engine and associate a connection with the context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
