from __future__ import annotations

from httpx import AsyncClient
import pytest


async def _post_chat(client: AsyncClient, auth_headers: dict[str, str], content: str) -> dict:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": content}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()


async def test_investment_decision_creates_investigation(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    body = await _post_chat(
        client,
        auth_headers,
        "Use RAG and internal policy documents to explain whether NVDA should be trimmed.",
    )
    assert body["answer_type"] == "investment_decision"
    assert body.get("investigation_id")

    listed = await client.get("/investigations", headers=auth_headers)
    assert listed.status_code == 200
    investigations = listed.json()
    assert len(investigations) == 1
    record = investigations[0]
    assert record["id"] == body["investigation_id"]
    assert record["conversation_id"] == body["conversation_id"]
    assert record["source_response_id"] == body["response_id"]


async def test_app_help_does_not_create_investigation(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    body = await _post_chat(client, auth_headers, "How many languages do you support?")
    assert body["answer_type"] == "app_help"
    assert body.get("investigation_id") is None
    listed = await client.get("/investigations", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json() == []


async def test_out_of_scope_does_not_create_investigation(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    body = await _post_chat(client, auth_headers, "What is the weather tomorrow?")
    assert body["answer_type"] == "out_of_scope"
    assert body.get("investigation_id") is None
    listed = await client.get("/investigations", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json() == []


async def test_get_and_list_are_user_scoped(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await _post_chat(client, auth_headers, "Review portfolio policy breaches and recommend action.")
    assert created["investigation_id"] is not None

    second = await client.post(
        "/auth/register",
        json={
            "email": "investigation.other@example.com",
            "password": "Password123!",
            "full_name": "Other User",
        },
    )
    assert second.status_code == 200
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    other_list = await client.get("/investigations", headers=second_headers)
    assert other_list.status_code == 200
    assert other_list.json() == []

    forbidden = await client.get(f"/investigations/{created['investigation_id']}", headers=second_headers)
    assert forbidden.status_code == 404


async def test_get_detail_returns_full_investigation_fields(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await _post_chat(
        client,
        auth_headers,
        "Use RAG and internal policy documents to explain whether NVDA should be trimmed.",
    )
    investigation_id = created["investigation_id"]
    assert investigation_id

    detail = await client.get(f"/investigations/{investigation_id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert isinstance(body["tools_used"], list)
    assert isinstance(body["evidence_items"], list)
    assert isinstance(body["rag_sources"], list)
    assert body["summary"]


async def test_delete_investigation_removes_it_from_list(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await _post_chat(client, auth_headers, "Review market and policy risks for NVDA.")
    investigation_id = created["investigation_id"]
    assert investigation_id

    deleted = await client.delete(f"/investigations/{investigation_id}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = await client.get("/investigations", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json() == []


async def test_investigation_links_existing_approval_id_when_present(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    body = await _post_chat(
        client,
        auth_headers,
        "Use policy and portfolio evidence to recommend trimming NVDA concentration immediately.",
    )
    assert body["answer_type"] == "investment_decision"
    assert body.get("decision") is not None
    approval_id = body["decision"].get("approval_id")
    if not approval_id:
        pytest.skip("Approval gate did not trigger for this recommendation in current deterministic policy.")
    detail = await client.get(f"/investigations/{body['investigation_id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["approval_id"] == approval_id

