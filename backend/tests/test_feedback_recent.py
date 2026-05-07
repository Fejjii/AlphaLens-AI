from __future__ import annotations

from httpx import AsyncClient


async def test_feedback_recent_endpoint_returns_latest_items(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    payload = {
        "conversation_id": "conv_test",
        "response_id": "msg_test",
        "rating": "thumbs_up",
        "category": "usefulness",
        "comment": "Clear and actionable.",
    }
    create = await client.post("/feedback", json=payload, headers=auth_headers)
    assert create.status_code == 200

    recent = await client.get("/feedback/recent", headers=auth_headers)
    assert recent.status_code == 200
    body = recent.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["response_id"] == "msg_test"
    assert body[0]["rating"] == "thumbs_up"
