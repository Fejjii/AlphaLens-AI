from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.database import Base
from alphalens.repositories.approvals import (
    InMemoryApprovalRepository,
    SqlAlchemyApprovalRepository,
)
from alphalens.schemas.agent import AgentDecision, EvidenceItem, Recommendation, RiskLevel
from alphalens.schemas.approval import (
    ApprovalActionType,
    ApprovalDecision,
    ApprovalRecord,
    ApprovalStatus,
)
from alphalens.services.approvals_service import ApprovalsService


def _sample_record(approval_id: str = "apv_test_1") -> ApprovalRecord:
    return ApprovalRecord(
        approval_id=approval_id,
        created_at=datetime.now(tz=UTC),
        status=ApprovalStatus.PENDING,
        action_type=ApprovalActionType.BUY,
        asset="NVDA",
        recommendation=Recommendation.BUY,
        rationale="Sample rationale",
        evidence=[
            EvidenceItem(
                tool="market_quote",
                summary="Fetched quote",
                data={"quotes": [{"ticker": "NVDA", "price": 750.0}]},
            )
        ],
        risk_level="medium",
        confidence=0.65,
    )


def _sqlite_session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def test_in_memory_repository_create_list_get_update() -> None:
    repo = InMemoryApprovalRepository()
    record = _sample_record()

    created = repo.create(record)
    fetched = repo.get(record.approval_id)
    listed = repo.list()

    assert created.approval_id == record.approval_id
    assert fetched is not None
    assert fetched.status is ApprovalStatus.PENDING
    assert len(listed) == 1

    updated = record.model_copy(
        update={
            "status": ApprovalStatus.APPROVED,
            "reviewer_note": "Looks good.",
            "decided_at": datetime.now(tz=UTC),
        }
    )
    repo.update(updated)
    saved = repo.get(record.approval_id)
    assert saved is not None
    assert saved.status is ApprovalStatus.APPROVED
    assert saved.reviewer_note == "Looks good."
    assert saved.decided_at is not None


def test_approval_service_works_with_repository() -> None:
    repo = InMemoryApprovalRepository()
    service = ApprovalsService(repository=repo)
    decision = AgentDecision(
        intent="trade_idea",
        recommendation=Recommendation.BUY,
        reasoning=["Buy NVDA based on trend and setup."],
        evidence=[
            EvidenceItem(
                tool="market_quote",
                summary="Fetched latest quote.",
                data={"quotes": [{"ticker": "NVDA", "price": 750.0}]},
            )
        ],
        requires_approval=True,
        risk_level=RiskLevel.MEDIUM,
        confidence=0.65,
    )

    record = service.create_approval_from_decision(decision)
    assert record.approval_id.startswith("apv_")
    assert service.get_approval(record.approval_id) is not None
    assert len(service.list_approvals()) == 1

    decided = service.decide_approval(
        record.approval_id,
        ApprovalDecision(status=ApprovalStatus.APPROVED, reviewer_note="Approved"),
    )
    assert decided is not None
    assert decided.status is ApprovalStatus.APPROVED
    assert decided.reviewer_note == "Approved"
    assert decided.decided_at is not None


def test_sqlalchemy_repository_persists_approval_with_sqlite() -> None:
    repo = SqlAlchemyApprovalRepository(_sqlite_session_factory())
    record = _sample_record("apv_sql_1")
    repo.create(record)

    fetched = repo.get("apv_sql_1")
    assert fetched is not None
    assert fetched.approval_id == "apv_sql_1"
    assert fetched.recommendation is Recommendation.BUY
    assert fetched.evidence[0].tool == "market_quote"


def test_sqlalchemy_repository_decision_update_persists_note_and_decided_at() -> None:
    repo = SqlAlchemyApprovalRepository(_sqlite_session_factory())
    record = _sample_record("apv_sql_2")
    repo.create(record)
    decided_at = datetime.now(tz=UTC)
    updated = record.model_copy(
        update={
            "status": ApprovalStatus.REJECTED,
            "reviewer_note": "Need more downside analysis.",
            "decided_at": decided_at,
        }
    )

    repo.update(updated)
    saved = repo.get("apv_sql_2")
    assert saved is not None
    assert saved.status is ApprovalStatus.REJECTED
    assert saved.reviewer_note == "Need more downside analysis."
    # SQLite stores naive datetimes even when timezone=True.
    assert saved.decided_at is not None
    assert saved.decided_at.replace(tzinfo=UTC) == decided_at
