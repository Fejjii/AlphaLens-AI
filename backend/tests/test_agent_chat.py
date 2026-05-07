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
    assert decision["intent"] in {"portfolio_review", "portfolio_performance", "risk_review"}
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


async def test_policy_breach_prompt_routes_to_policy_breach(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Which policy rules are currently breached by the portfolio?"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["analysis"]["intent"] == "policy_breach_check"
    assert "Policy breach check" in body["message"]["content"]
    assert "portfolio_analyze" in body["used_tools"]
    assert "risk_check" in body["used_tools"]
    assert "threshold" in body["message"]["content"].lower()


async def test_performance_prompt_routes_to_portfolio_performance(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "What has been the performance of the portfolio in the last 1 month?"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["analysis"]["intent"] == "portfolio_performance"
    assert "Portfolio performance snapshot" in body["message"]["content"]
    assert "current nav" in body["message"]["content"].lower()
    assert "estimated 1m return" in body["message"]["content"].lower()
    assert "market_quote" in body["used_tools"]


async def test_rag_policy_prompt_returns_rag_sources(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "Use RAG and internal policy documents to explain whether NVDA should be trimmed.",
                }
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["analysis"]["intent"] in {"rag_policy_question", "investment_recommendation"}
    assert "rag_retrieve" in body["used_tools"]
    assert body["analysis"]["rag_status"] == "used"
    assert isinstance(body["analysis"]["rag_sources"], list)
    assert len(body["analysis"]["rag_sources"]) > 0
    assert (
        "policy summary from knowledge base" in body["message"]["content"].lower()
        or "investment recommendation" in body["message"]["content"].lower()
    )


async def test_policy_summary_prompt_uses_rag_context(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Summarize the internal investment policy from the knowledge base."}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["analysis"]["intent"] == "rag_policy_question"
    assert "rag_retrieve" in body["used_tools"]
    assert body["analysis"]["rag_status"] == "used"
    assert len(body["analysis"]["rag_sources"]) > 0


async def test_explicit_kb_phrase_forces_rag_trigger(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Source from KB: summarize policy limits for single-name concentration."}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "rag_retrieve" in body["used_tools"]
    assert body["analysis"]["rag_status"] in {"used", "no_results"}
