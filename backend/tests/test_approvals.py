from __future__ import annotations

from httpx import AsyncClient

from alphalens.api import deps
from alphalens.schemas.agent import (
    AgentDecision,
    EvidenceItem,
    Recommendation,
    RiskLevel,
)


def _seed_pending_approval() -> str:
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
        )
    )
    return record.approval_id


async def test_list_approvals(client: AsyncClient) -> None:
    approval_id = _seed_pending_approval()
    response = await client.get("/approvals", params={"status": "pending"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["approval_id"] == approval_id
    assert body[0]["status"] == "pending"


async def test_get_approval_by_id(client: AsyncClient) -> None:
    approval_id = _seed_pending_approval()

    response = await client.get(f"/approvals/{approval_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["approval_id"] == approval_id
    assert body["action_type"] == "buy"


async def test_approve_approval(client: AsyncClient) -> None:
    approval_id = _seed_pending_approval()

    response = await client.post(
        f"/approvals/{approval_id}/decision",
        json={"status": "approved", "reviewer_note": "Reviewed and accepted."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approval_id"] == approval_id
    assert body["status"] == "approved"
    assert body["reviewer_note"] == "Reviewed and accepted."
    assert body["decided_at"] is not None


async def test_reject_approval(client: AsyncClient) -> None:
    approval_id = _seed_pending_approval()

    response = await client.post(
        f"/approvals/{approval_id}/decision",
        json={"status": "rejected", "reviewer_note": "Not aligned with mandate."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["reviewer_note"] == "Not aligned with mandate."


async def test_needs_more_analysis_flow(client: AsyncClient) -> None:
    approval_id = _seed_pending_approval()

    response = await client.post(
        f"/approvals/{approval_id}/decision",
        json={
            "status": "needs_more_analysis",
            "reviewer_note": "Add downside scenario analysis.",
        },
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

    record = service.create_approval_from_decision(decision)

    assert record.risk_level == "high"
    assert record.confidence == 0.85


async def test_invalid_approval_id_returns_404(client: AsyncClient) -> None:
    response = await client.get("/approvals/apv_missing")
    assert response.status_code == 404

    response = await client.post(
        "/approvals/apv_missing/decision",
        json={"status": "approved"},
    )
    assert response.status_code == 404
