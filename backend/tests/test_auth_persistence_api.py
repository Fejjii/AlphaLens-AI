from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine

from alphalens.api import deps
from alphalens.api.main import create_app
from alphalens.core.config import get_settings
from alphalens.infrastructure.database import Base


def _clear_auth_dependency_caches() -> None:
    get_settings.cache_clear()
    deps._persistence_runtime_state.cache_clear()
    deps._user_repository.cache_clear()
    deps._refresh_token_repository.cache_clear()
    deps._auth_service.cache_clear()


async def _post_json(path: str, payload: dict[str, str], *, cookies: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies=cookies,
    ) as client:
        response = await client.post(path, json=payload)
    return response.status_code, response.json()


async def _post_without_json(path: str, *, cookies: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies=cookies,
    ) as client:
        response = await client.post(path)
    return response.status_code, response.json()


@pytest.mark.asyncio
async def test_auth_endpoints_persist_across_app_restarts(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'auth_api_persistence.sqlite3'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "postgres")
    monkeypatch.setenv("APP_DATABASE_URL", database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(bind=engine)

    _clear_auth_dependency_caches()
    register_status, register_payload = await _post_json(
        "/auth/register",
        {
            "email": "persisted@example.com",
            "password": "Password123!",
            "full_name": "Persisted User",
        },
    )
    assert register_status == 200
    refresh_token = str(register_payload["refresh_token"])

    _clear_auth_dependency_caches()
    login_status, login_payload = await _post_json(
        "/auth/login",
        {"email": "persisted@example.com", "password": "Password123!"},
    )
    assert login_status == 200
    assert login_payload["user"]["email"] == "persisted@example.com"

    _clear_auth_dependency_caches()
    refresh_status, _ = await _post_without_json(
        "/auth/refresh",
        cookies={"alphalens_refresh_token": refresh_token},
    )
    assert refresh_status == 200

    _clear_auth_dependency_caches()
    logout_status, logout_payload = await _post_without_json(
        "/auth/logout",
        cookies={"alphalens_refresh_token": refresh_token},
    )
    assert logout_status == 200
    assert logout_payload["logged_out"] is True

    _clear_auth_dependency_caches()
    expired_status, expired_payload = await _post_without_json(
        "/auth/refresh",
        cookies={"alphalens_refresh_token": refresh_token},
    )
    assert expired_status == 401
    assert expired_payload["detail"] == "Session expired."
