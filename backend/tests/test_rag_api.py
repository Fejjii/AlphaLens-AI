from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from alphalens.api import deps as api_deps
from alphalens.api.main import create_app
from alphalens.core.config import Settings, get_settings


@pytest.fixture
async def kb_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    (tmp_path / "policy.md").write_text(
        "# Investment Policy\n\n"
        "## Sector limits\n\nSemiconductors max 35 percent of NAV.\n",
        encoding="utf-8",
    )
    (tmp_path / "risk.md").write_text(
        "# Risk Playbook\n\n"
        "## Drawdown\n\nMax drawdown threshold negative 15 percent over 12 months.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("RAG_COLLECTION", "kb_api_test")
    monkeypatch.delenv("QDRANT_URL", raising=False)

    get_settings.cache_clear()
    api_deps._rag_service.cache_clear()
    api_deps._chat_service.cache_clear()

    app = create_app(Settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    get_settings.cache_clear()
    api_deps._rag_service.cache_clear()
    api_deps._chat_service.cache_clear()


async def test_rag_test_returns_chunks(kb_client: AsyncClient) -> None:
    response = await kb_client.get(
        "/rag/test", params={"query": "sector limit semiconductors", "k": 3}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "sector limit semiconductors"
    assert body["k"] == 3
    assert isinstance(body["chunks"], list)
    assert body["chunks"], "expected at least one chunk"
    top = body["chunks"][0]
    assert top["source"] == "policy.md"
    assert "source" in top and "heading" in top and "text" in top
    assert 0.0 <= top["score"] <= 1.0


async def test_rag_test_validates_query(kb_client: AsyncClient) -> None:
    response = await kb_client.get("/rag/test", params={"query": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
