from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from alphalens.api import deps
from alphalens.api.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    deps._approval_repository.cache_clear()
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
    deps._scenarios_service.cache_clear()
    deps._scenario_repository.cache_clear()
    deps._cache_service.cache_clear()
    deps._memory_service.cache_clear()
    app = create_app()
    deps.get_approvals_service().reset()
    deps.get_usage_service().reset()
    deps.get_reports_service().reset()
    deps.get_scenarios_service().reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    deps.get_approvals_service().reset()
    deps.get_usage_service().reset()
    deps._approval_repository.cache_clear()
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
    deps._scenarios_service.cache_clear()
    deps._scenario_repository.cache_clear()
    deps._cache_service.cache_clear()
    deps._memory_service.cache_clear()
