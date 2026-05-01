from __future__ import annotations

from httpx import AsyncClient

from alphalens.api import deps
from alphalens.schemas.agent import (
    AgentDecision,
    EvidenceItem,
    Recommendation,
    RiskLevel,
)

def _seed_pending_approval(*, user_id: str) -> str:
    service = deps.get_approvals_service()
    record = service.create_approval_from_decision(
        AgentDecision(
            intent="trade_idea",
            recommendation=Recommendation.BUY,
            reasoning=["Buy NVDA based on the latest market evidence."],
            evidence=[
                EvidenceItem(
                    tool="market_quote",
                    summary="Fetched latest NVDA quote.",
                    data={"quotes": [{"ticker": "NVDA", "price": 750.0}]},
                )
            ],
            requires_approval=True,
        ),
        user_id=user_id,
    )
    return record.approval_id


async def test_list_approvals(
    client: AsyncClient,
    auth_session: dict[str, object],
) -> None:
    user_id = str(auth_session["user"]["id"])  # type: ignore[index]
    auth_headers = auth_session["headers"]  # type: ignore[assignment]
    approval_id = _seed_pending_approval(user_id=user_id)
    response = await client.get("/approvals", params={"status": "pending"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["approval_id"] == approval_id
    assert body[0]["status"] == "pending"


async def test_get_approval_by_id(client: AsyncClient, auth_session: dict[str, object]) -> None:
    user_id = str(auth_session["user"]["id"])  # type: ignore[index]
    auth_headers = auth_session["headers"]  # type: ignore[assignment]
    approval_id = _seed_pending_approval(user_id=user_id)

    response = await client.get(f"/approvals/{approval_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["approval_id"] == approval_id
    assert body["action_type"] == "buy"


async def test_approve_approval(client: AsyncClient, auth_session: dict[str, object]) -> None:
    user_id = str(auth_session["user"]["id"])  # type: ignore[index]
    auth_headers = auth_session["headers"]  # type: ignore[assignment]
    approval_id = _seed_pending_approval(user_id=user_id)

    response = await client.post(
        f"/approvals/{approval_id}/decision",
        json={"status": "approved", "reviewer_note": "Reviewed and accepted."},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approval_id"] == approval_id
    assert body["status"] == "approved"
    assert body["reviewer_note"] == "Reviewed and accepted."
    assert body["decided_at"] is not None


async def test_reject_approval(client: AsyncClient, auth_session: dict[str, object]) -> None:
    user_id = str(auth_session["user"]["id"])  # type: ignore[index]
    auth_headers = auth_session["headers"]  # type: ignore[assignment]
    approval_id = _seed_pending_approval(user_id=user_id)

    response = await client.post(
        f"/approvals/{approval_id}/decision",
        json={"status": "rejected", "reviewer_note": "Not aligned with mandate."},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["reviewer_note"] == "Not aligned with mandate."


async def test_needs_more_analysis_flow(
    client: AsyncClient,
    auth_session: dict[str, object],
) -> None:
    user_id = str(auth_session["user"]["id"])  # type: ignore[index]
    auth_headers = auth_session["headers"]  # type: ignore[assignment]
    approval_id = _seed_pending_approval(user_id=user_id)

    response = await client.post(
        f"/approvals/{approval_id}/decision",
        json={
            "status": "needs_more_analysis",
            "reviewer_note": "Add downside scenario analysis.",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_more_analysis"
    assert body["reviewer_note"] == "Add downside scenario analysis."


async def test_approval_record_copies_risk_level_and_confidence_from_decision() -> None:
    deps._approvals_service.cache_clear()
    service = deps.get_approvals_service()
    service.reset()
    decision = AgentDecision(
        intent="risk_check",
        recommendation=Recommendation.ESCALATE,
        reasoning=["Single-name concentration breach."],
        evidence=[
            EvidenceItem(tool="risk_check", summary="violations", data={"status": "violations"})
        ],
        requires_approval=True,
        risk_level=RiskLevel.HIGH,
        confidence=0.85,
    )

    record = service.create_approval_from_decision(decision, user_id="usr_local_test")

    assert record.risk_level == "high"
    assert record.confidence == 0.85


async def test_invalid_approval_id_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/approvals/apv_missing", headers=auth_headers)
    assert response.status_code == 404

    response = await client.post(
        "/approvals/apv_missing/decision",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert response.status_code == 404
