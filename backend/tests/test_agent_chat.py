from __future__ import annotations

from httpx import AsyncClient


async def test_agent_chat_returns_assistant_message(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    payload = {
        "messages": [
            {"role": "user", "content": "How is my portfolio doing today?"}
        ]
    }
    response = await client.post("/agent/chat", json=payload, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"].startswith("conv_")
    assert body["response_id"].startswith("msg_")
    assert body["message"]["role"] == "assistant"
    assert isinstance(body["message"]["content"], str)
    assert len(body["message"]["content"]) > 0

    decision = body["decision"]
    assert decision is not None
    assert decision["intent"] == "portfolio_review"
    assert decision["recommendation"] in {
        "inform", "hold", "buy", "sell", "trim", "rebalance", "escalate"
    }
    assert isinstance(decision["reasoning"], list)
    assert isinstance(decision["evidence"], list)
    assert isinstance(decision["requires_approval"], bool)
    assert decision["risk_level"] in {"low", "medium", "high", "critical"}
    assert isinstance(decision["confidence"], float)
    assert 0.0 <= decision["confidence"] <= 1.0


async def test_chat_alias_matches_agent_chat_contract(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    payload = {
        "messages": [
            {"role": "user", "content": "Give me a concise market update."}
        ]
    }
    response = await client.post("/chat", json=payload, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"].startswith("conv_")
    assert body["message"]["role"] == "assistant"


async def test_agent_chat_validation_error(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post("/agent/chat", json={"messages": []}, headers=auth_headers)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
