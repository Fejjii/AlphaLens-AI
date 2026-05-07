from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch

from alphalens.api import deps
from alphalens.api.main import create_app
from alphalens.core.config import get_settings


async def _runtime_status_payload(
    monkeypatch: MonkeyPatch,
    *,
    app_env: str,
    persistence_backend: str,
    app_database_url: str | None,
) -> dict[str, object]:
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("PERSISTENCE_BACKEND", persistence_backend)
    if app_database_url is None:
        monkeypatch.delenv("APP_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("APP_DATABASE_URL", app_database_url)
        monkeypatch.setenv("DATABASE_URL", app_database_url)

    get_settings.cache_clear()
    deps._persistence_runtime_state.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/runtime/status")
    assert response.status_code == 200
    get_settings.cache_clear()
    deps._persistence_runtime_state.cache_clear()
    return response.json()


@pytest.mark.asyncio
async def test_runtime_status_reports_connected_postgres_state(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    payload = await _runtime_status_payload(
        monkeypatch=monkeypatch,
        app_env="test",
        persistence_backend="postgres",
        app_database_url=f"sqlite+pysqlite:///{tmp_path / 'runtime_connected.sqlite3'}",
    )

    persistence = next(item for item in payload["providers"] if item["name"] == "Persistence")
    assert persistence["status"] == "connected"
    assert payload["data_sources"]["users"] == "postgres"
    assert payload["data_sources"]["refresh_tokens"] == "postgres"
    assert payload["data_sources"]["approvals"] == "postgres"
    assert payload["data_sources"]["reports"] == "postgres"
    assert payload["data_sources"]["feedback"] == "postgres"
    assert payload["data_sources"]["usage"] == "postgres"


@pytest.mark.asyncio
async def test_runtime_status_reports_memory_fallback_when_database_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    payload = await _runtime_status_payload(
        monkeypatch=monkeypatch,
        app_env="test",
        persistence_backend="postgres",
        app_database_url=None,
    )

    persistence = next(item for item in payload["providers"] if item["name"] == "Persistence")
    assert persistence["status"] == "memory_fallback"
    assert payload["data_sources"]["users"] == "memory"
    assert payload["data_sources"]["refresh_tokens"] == "memory"
    assert payload["data_sources"]["approvals"] == "memory"
    assert payload["data_sources"]["reports"] == "memory"
    assert payload["data_sources"]["feedback"] == "memory"
    assert payload["data_sources"]["usage"] == "memory"
