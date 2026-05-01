from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alphalens.infrastructure.database import Base
from alphalens.infrastructure.models import FeedbackModel
from alphalens.repositories.feedback import SqlAlchemyFeedbackRepository
from alphalens.repositories.reports import SqlAlchemyReportRepository
from alphalens.repositories.scenarios import SqlAlchemyScenarioRepository
from alphalens.repositories.usage import SqlAlchemyUsageRepository
from alphalens.schemas.feedback import FeedbackCreate, FeedbackRating
from alphalens.schemas.report import ReportCreate, ReportResponse, ReportSection, ReportType
from alphalens.schemas.scenario import ScenarioCreate, ScenarioImpactItem, ScenarioResponse, ScenarioType
from alphalens.schemas.usage import UsageEvent
from alphalens.services.feedback_service import FeedbackService
from alphalens.services.reports_service import ReportsService
from alphalens.services.scenarios_service import ScenariosService
from alphalens.services.usage_service import UsageService


def _session_factory() -> sessionmaker:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def test_sqlalchemy_repositories_enforce_user_scoping() -> None:
    factory = _session_factory()
    feedback_repo = SqlAlchemyFeedbackRepository(factory)
    reports_repo = SqlAlchemyReportRepository(factory)
    scenarios_repo = SqlAlchemyScenarioRepository(factory)

    feedback_repo.create(
        FeedbackService().create_feedback(
            FeedbackCreate(conversation_id="conv", rating=FeedbackRating.THUMBS_UP),
            user_id="user_a",
        )
    )
    feedback_repo.create(
        FeedbackService().create_feedback(
            FeedbackCreate(conversation_id="conv", rating=FeedbackRating.THUMBS_DOWN),
            user_id="user_b",
        )
    )

    report = ReportResponse(
        id="rpt_1",
        user_id="user_a",
        title="T",
        report_type=ReportType.INVESTMENT_MEMO,
        sections=[ReportSection(key="k", title="t", content="c")],
        evidence=[],
        citations=[],
    )
    reports_repo.create(report)
    scenarios_repo.create(
        ScenarioResponse(
            id="scn_1",
            user_id="user_a",
            title="S",
            scenario_type=ScenarioType.PRICE_SHOCK,
            assumptions=[],
            portfolio_impact=1.0,
            affected_holdings=[ScenarioImpactItem(symbol="A", current_value_usd=1, shocked_value_usd=1, delta_usd=0, delta_pct=0)],
            risk_level="low",
            recommendation="ok",
            approval_required=False,
        )
    )

    assert len(feedback_repo.list(user_id="user_a")) == 1
    assert len(reports_repo.list(user_id="user_a")) == 1
    assert len(scenarios_repo.list(user_id="user_a")) == 1
    assert feedback_repo.list(user_id="user_b")[0].user_id == "user_b"
    assert reports_repo.get("rpt_1", user_id="user_b") is None
    assert scenarios_repo.get("scn_1", user_id="user_b") is None


def test_sqlalchemy_usage_aggregates_events() -> None:
    factory = _session_factory()
    repo = SqlAlchemyUsageRepository(factory)
    service = UsageService(repository=repo)
    service.record_llm_usage(
        event_type="llm_call",
        provider="openai",
        user_id="user_a",
        input_tokens=100,
        output_tokens=50,
        model="gpt-4o-mini",
    )
    service.record_tool_usage(tool_name="portfolio_analyze", success=True, provider="fallback", user_id="user_a")
    service.record_event(event_type="cache_hit", provider="cache", user_id="user_b")

    summary = service.get_usage_summary(user_id="user_a")
    assert summary.total_events == 2
    assert summary.llm_calls == 1
    assert summary.tool_calls == 1
    assert summary.estimated_cost_usd > 0


def test_sqlalchemy_memory_roundtrip() -> None:
    from alphalens.memory.sqlalchemy_memory import SqlAlchemyMemoryStore

    factory = _session_factory()
    store = SqlAlchemyMemoryStore(factory)
    store.save_conversation(
        "conv_1",
        {"messages": [{"role": "user", "content": "hi"}], "metadata": [{"x": 1}], "user_id": "user_a"},
    )
    history = store.get_conversation("conv_1")
    assert history is not None
    assert history["messages"][0]["content"] == "hi"
