"""Async database setup using SQLAlchemy 2.0 with aiosqlite.

Provides engine creation, session management, and table initialization.
"""

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy models."""

    pass


_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """Get or create the async SQLAlchemy engine.

    Returns:
        AsyncEngine: The database engine instance.
    """
    global _engine
    if _engine is None:
        from core.config import get_settings

        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory.

    Returns:
        async_sessionmaker: Session factory for creating database sessions.
    """
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def init_db() -> None:
    """Initialize the database by creating all tables.

    Creates all tables defined in models that inherit from Base.
    Safe to call multiple times as it uses CREATE IF NOT EXISTS.
    """
    from core import models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session.

    Yields an AsyncSession and ensures it is closed after use.

    Yields:
        AsyncSession: An active database session.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session
