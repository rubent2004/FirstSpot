"""Async SQLAlchemy 2.0 database engine, session factory, and PostGIS verification."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an asynchronous database session for request dependency injection."""
    async with async_session_factory() as session:
        yield session


async def verify_postgis_connection(session: AsyncSession) -> str:
    """Verify PostGIS availability and return the full PostGIS version string."""
    result = await session.execute(text("SELECT PostGIS_Full_Version();"))
    version = result.scalar_one()
    return str(version)
