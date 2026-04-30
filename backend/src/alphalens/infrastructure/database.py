"""SQLAlchemy 2.0 database primitives."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from alphalens.core.config import Settings


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


def _database_url(settings: Settings) -> str | None:
    return settings.app_database_url or settings.database_url


def create_engine_from_settings(settings: Settings) -> Engine:
    """Create an SQLAlchemy engine from settings."""
    url = _database_url(settings)
    if not url:
        raise ValueError("Database URL is not configured.")
    return create_engine(url, future=True, pool_pre_ping=True)


def get_session_factory(settings: Settings) -> sessionmaker[Session]:
    """Build a session factory for the configured engine."""
    engine = create_engine_from_settings(settings)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
