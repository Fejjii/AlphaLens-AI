from __future__ import annotations

from httpx import AsyncClient


async def test_portfolio_summary(client: AsyncClient) -> None:
    response = await client.get("/portfolio/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"]
    assert body["nav"]["currency"] == "USD"
    assert isinstance(body["positions"], list)
    assert len(body["positions"]) >= 1
    assert isinstance(body["risk_metrics"], list)
