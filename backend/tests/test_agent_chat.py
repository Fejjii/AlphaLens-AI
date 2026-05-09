from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from alphalens.api import deps
from alphalens.schemas.user import UserProfile


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
    assert body["answer_type"] == "investment_decision"
    assert body["analysis"]["intent"] in {"rag_policy_question", "investment_recommendation"}
    assert "rag_retrieve" in body["used_tools"]
    assert body["analysis"]["rag_status"] == "used"
    assert isinstance(body["analysis"]["rag_sources"], list)
    assert len(body["analysis"]["rag_sources"]) > 0
    final = body["analysis"]["final_answer"]
    assert "policy summary from knowledge base" not in final.lower()
    assert final.lower().count(".md") == 0
    rag_ev = [e for e in body["decision"]["evidence"] if e["tool"] == "rag_retrieve"]
    assert rag_ev, "expected per-source RAG evidence rows"
    assert any(len(e["summary"]) > 20 for e in rag_ev)
    titles = {rs["document_title"] for rs in body["analysis"]["rag_sources"]}
    assert len(titles) > 0


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
    assert body["answer_type"] == "investment_decision"
    assert body["analysis"]["intent"] == "rag_policy_question"
    assert "rag_retrieve" in body["used_tools"]
    assert body["analysis"]["rag_status"] == "used"
    assert len(body["analysis"]["rag_sources"]) > 0
    final = body["analysis"]["final_answer"]
    assert "policy summary from knowledge base" not in final.lower()
    assert ".md" not in final.lower()
    assert body["analysis"]["rag_sources"][0].get("snippet")


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


async def test_app_help_includes_routing_metadata(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "How many languages do you support?"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "app_help"
    assert "routing" in body
    assert body["routing"]["answer_type"] == "app_help"
    assert body["routing"]["suggested_tools"] == []
    assert body["decision"] is None
    content = body["message"]["content"].lower()
    assert "english" in content and "arabic" in content
    assert body["analysis"]["rag_sources"] == []
    assert body["analysis"]["provider_modes"] == []


async def test_app_help_approvals_workflow_is_distinct_from_languages(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    r1 = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "How many languages do you support?"}]},
        headers=auth_headers,
    )
    r2 = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "How do approvals work?"}]},
        headers=auth_headers,
    )
    assert r1.status_code == 200 and r2.status_code == 200
    b1, b2 = r1.json(), r2.json()
    assert b1["answer_type"] == "app_help" == b2["answer_type"]
    t1, t2 = b1["message"]["content"], b2["message"]["content"]
    assert t1 != t2
    low = t2.lower()
    assert "approval" in low
    assert any(w in low for w in ("approve", "reject", "human", "checkpoint", "request"))


async def test_sequential_app_help_in_one_conversation_stays_specific(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    conv = None
    for prompt, needle in (
        ("How many languages do you support?", "english"),
        ("How do approvals work?", "approval"),
    ):
        payload: dict = {"messages": [{"role": "user", "content": prompt}]}
        if conv:
            payload["conversation_id"] = conv
        res = await client.post("/agent/chat", json=payload, headers=auth_headers)
        assert res.status_code == 200
        body = res.json()
        conv = body["conversation_id"]
        assert needle in body["message"]["content"].lower()


async def test_clarification_should_i_without_investment_context(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Should I do it?"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "clarification"
    assert body["decision"] is None
    assert body["used_tools"] == []
    assert "portfolio action" in body["message"]["content"].lower()


async def test_non_investment_never_returns_decision_or_provider_metadata(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "What is the weather tomorrow?"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "out_of_scope"
    assert body["decision"] is None
    assert body["analysis"]["provider_modes"] == []
    assert body["analysis"]["rag_sources"] == []


async def test_french_capability_question_returns_app_help_without_decision(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "Est ce que tu comprends en français ? Est ce que tu me comprends en français ?",
                }
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "app_help"
    assert body["decision"] is None
    assert body["used_tools"] == []
    content = body["message"]["content"]
    lowered = content.lower()
    assert "français" in lowered or "francais" in lowered or "alphalens" in lowered


async def test_weather_question_returns_out_of_scope(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "What is the weather tomorrow?"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "out_of_scope"
    assert body["decision"] is None
    assert body["used_tools"] == []


async def test_portfolio_performance_returns_investment_decision_answer_type(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "What has been the performance of the portfolio in the last 1 month?",
                }
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "investment_decision"
    assert body["decision"] is not None


async def test_rag_policy_question_returns_investment_decision_answer_type(
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
    assert body["answer_type"] == "investment_decision"
    assert "rag_retrieve" in body["used_tools"]


async def test_nvda_scenario_shock_returns_200(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={
            "messages": [
                {"role": "user", "content": "What happens if NVDA drops 10 percent?"},
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "investment_decision"
    assert body["analysis"]["intent"] == "scenario_simulation"
    text = body["message"]["content"].lower()
    assert "nvda" in text
    assert "10" in body["message"]["content"]
    assert "portfolio" in text or "weight" in text or "impact" in text


async def test_msft_scenario_shock_returns_200(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "How would a 15 percent MSFT drop affect the portfolio?",
                }
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "investment_decision"
    assert body["analysis"]["intent"] == "scenario_simulation"
    assert "msft" in body["message"]["content"].lower()


async def test_semiconductor_sector_shock_returns_200(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={
            "messages": [
                {"role": "user", "content": "What if semiconductors fall 20 percent?"},
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "investment_decision"
    assert "20" in body["message"]["content"] or "scenario" in body["message"]["content"].lower()


async def test_agent_chat_expired_token_returns_401_json(
    client: AsyncClient,
    auth_session: dict[str, object],
) -> None:
    user = UserProfile.model_validate(auth_session["user"])
    auth = deps.get_auth_service()
    expired = auth.build_test_access_token(
        user,
        expires_at=datetime.now(tz=UTC) - timedelta(minutes=30),
    )
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("error") == "token_expired"


async def test_investigation_create_failure_does_not_fail_chat(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = deps.get_investigations_service()

    def _raise(**_kwargs: object) -> None:
        raise RuntimeError("investigation persist failed")

    monkeypatch.setattr(svc, "create_from_chat_response", _raise)
    response = await client.post(
        "/agent/chat",
        json={
            "messages": [
                {"role": "user", "content": "What happens if NVDA drops 10 percent?"},
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("investigation_id") is None
    assert "nvda" in body["message"]["content"].lower()
