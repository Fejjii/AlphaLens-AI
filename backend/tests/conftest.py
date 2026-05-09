from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from alphalens.api import deps
from alphalens.api.main import create_app
from alphalens.core.config import get_settings


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "in_memory")
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    deps._approval_repository.cache_clear()
    deps._persistence_runtime_state.cache_clear()
    deps._user_repository.cache_clear()
    deps._refresh_token_repository.cache_clear()
    deps._auth_service.cache_clear()
    deps._chat_service.cache_clear()
    deps._approvals_service.cache_clear()
    deps._rag_service.cache_clear()
    deps._llm_service.cache_clear()
    deps._market_data_service.cache_clear()
    deps._macro_service.cache_clear()
    deps._sec_service.cache_clear()
    deps._search_service.cache_clear()
    deps._usage_service.cache_clear()
    deps._feedback_service.cache_clear()
    deps._feedback_repository.cache_clear()
    deps._reports_service.cache_clear()
    deps._report_repository.cache_clear()
    deps._investigations_service.cache_clear()
    deps._investigation_repository.cache_clear()
    deps._scenarios_service.cache_clear()
    deps._scenario_repository.cache_clear()
    deps._usage_service.cache_clear()
    deps._cache_service.cache_clear()
    deps._memory_service.cache_clear()
    get_settings.cache_clear()
    app = create_app()
    deps.get_approvals_service().reset()
    deps.get_usage_service().reset()
    deps.get_investigations_service().reset()
    deps.get_reports_service().reset()
    deps.get_scenarios_service().reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    deps.get_approvals_service().reset()
    deps.get_usage_service().reset()
    deps._approval_repository.cache_clear()
    deps._persistence_runtime_state.cache_clear()
    deps._user_repository.cache_clear()
    deps._refresh_token_repository.cache_clear()
    deps._auth_service.cache_clear()
    deps._chat_service.cache_clear()
    deps._approvals_service.cache_clear()
    deps._rag_service.cache_clear()
    deps._llm_service.cache_clear()
    deps._market_data_service.cache_clear()
    deps._macro_service.cache_clear()
    deps._sec_service.cache_clear()
    deps._search_service.cache_clear()
    deps._usage_service.cache_clear()
    deps._feedback_service.cache_clear()
    deps._feedback_repository.cache_clear()
    deps._reports_service.cache_clear()
    deps._report_repository.cache_clear()
    deps._investigations_service.cache_clear()
    deps._investigation_repository.cache_clear()
    deps._scenarios_service.cache_clear()
    deps._scenario_repository.cache_clear()
    deps._usage_service.cache_clear()
    deps._cache_service.cache_clear()
    deps._memory_service.cache_clear()


@pytest.fixture
async def auth_session(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/auth/register",
        json={
            "email": "test.user@example.com",
            "password": "Password123!",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 200
    body = response.json()
    token = body["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user": body["user"],
    }


@pytest.fixture
async def auth_headers(auth_session: dict[str, object]) -> dict[str, str]:
    return auth_session["headers"]  # type: ignore[return-value]
