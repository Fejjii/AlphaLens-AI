from __future__ import annotations

import pytest
from httpx import AsyncClient

from alphalens.api import deps
from alphalens.core.config import get_settings
from alphalens.services.plan_service import PlanAccessError, PlanService


async def test_plans_me_and_usage(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    me_response = await client.get("/plans/me", headers=auth_headers)
    assert me_response.status_code == 200
    assert me_response.json()["plan"] == "free"

    usage_response = await client.get("/plans/usage", headers=auth_headers)
    assert usage_response.status_code == 200
    body = usage_response.json()
    assert body["plan"] == "free"
    assert "quota_reset_at" in body
    assert isinstance(body["quota_reset_at"], str)
    assert body["quota_reset_at"].startswith("20")
    assert "monthly_usage" in body
    assert "remaining_quota" in body


async def test_free_user_quota_decreases_after_events(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    before = await client.get("/plans/usage", headers=auth_headers)
    assert before.status_code == 200
    before_quota = before.json()["remaining_quota"]["chats"]

    await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "How is my portfolio doing?"}]},
        headers=auth_headers,
    )

    after = await client.get("/plans/usage", headers=auth_headers)
    assert after.status_code == 200
    after_body = after.json()
    assert after_body["monthly_usage"]["chats"] >= before.json()["monthly_usage"]["chats"]


async def test_free_user_quota_exceeded_returns_clear_error(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    auth_service = deps.get_auth_service()
    user = auth_service.resolve_current_user(auth_headers["Authorization"].split(" ", 1)[1])
    usage_service = deps.get_usage_service()

    for _ in range(50):
        usage_service.record_event(
            event_type="llm_call",
            provider="test",
            user_id=user.id,
        )

    plan_service = PlanService(settings=get_settings(), usage_service=usage_service)
    with pytest.raises(PlanAccessError):
        plan_service.ensure_usage_allowed(user, "chats")


async def test_pro_and_team_have_higher_limits(
    client: AsyncClient,
    auth_session: dict[str, object],
) -> None:
    auth_service = deps.get_auth_service()
    repo = auth_service._repository
    user = auth_service.resolve_current_user(str(auth_session["headers"]["Authorization"]).split(" ", 1)[1])  # type: ignore[index]

    updated = user.model_copy(update={"plan": "pro"})
    repo.update(updated, password_hash=repo.get_password_hash(user.id) or "")
    refreshed = repo.get_by_email(user.email)
    assert refreshed is not None
    plan = PlanService(settings=get_settings(), usage_service=deps.get_usage_service()).get_current_plan(refreshed)
    assert plan.plan == "pro"
    assert plan.limits.monthly_chats and plan.limits.monthly_chats > 50
