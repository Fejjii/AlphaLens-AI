"""Postgres engine placeholder.

We avoid creating a live engine here so importing the package never opens
a connection. Wire up SQLAlchemy / SQLModel when the persistence layer
lands.
"""

from __future__ import annotations

from alphalens.core.config import Settings


def get_database_url(settings: Settings) -> str | None:
    return settings.database_url
