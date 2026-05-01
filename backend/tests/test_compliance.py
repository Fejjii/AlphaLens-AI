from __future__ import annotations

from pathlib import Path

from alphalens.core.config import Settings
from alphalens.memory.service import MemoryService
from alphalens.memory.in_memory import InMemoryMemoryStore
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.schemas.report import ReportCreate
from alphalens.schemas.scenario import ScenarioCreate
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.rag_service import RAGService
from alphalens.services.reports_service import ReportsService
from alphalens.services.scenarios_service import ScenariosService
from alphalens.tools.registry import ToolRegistry


class _ComplianceStubGraph:
    def invoke(self, state, config=None):
        return {
            "intent": "portfolio_review",
            "recommendation": "buy",
            "reasoning": ["weak evidence"],
            "evidence": [],
            "requires_approval": False,
            "risk_level": "medium",
            "confidence": 0.4,
            "answer": "Proceed with caution.",
            "used_tools": [],
            "citations": [],
            "portfolio_impact": 40000,
        }


def _build_chat_service(tmp_path: Path) -> ChatService:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "note.md").write_text("# Note\n\nCompliance test.\n", encoding="utf-8")
    settings = Settings(knowledge_base_path=str(kb), rag_collection=f"compliance_{tmp_path.name}")
    return ChatService(
        settings=settings,
        rag_service=RAGService(settings),
        approvals_service=ApprovalsService(),
        registry=ToolRegistry(),
        memory_service=MemoryService(store=InMemoryMemoryStore(ttl_seconds=3600), enabled=True),
    )


def test_weak_evidence_requires_more_analysis(tmp_path: Path) -> None:
    service = _build_chat_service(tmp_path)
    service._graph = _ComplianceStubGraph()
    response = service.chat(ChatRequest(messages=[ChatMessage(role=ChatRole.USER, content="Should I buy?")]))

    assert response.decision is not None
    assert response.decision.recommendation.value == "needs_more_analysis"
    assert response.decision.requires_approval is True
    assert "missing_evidence" in response.decision.policy_flags
    assert response.decision.disclaimer


def test_report_includes_disclaimer(tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "note.md").write_text("# Note\n\nReport compliance test.\n", encoding="utf-8")
    settings = Settings(knowledge_base_path=str(kb), rag_collection=f"report_{tmp_path.name}")
    service = ReportsService(memory_service=MemoryService(store=InMemoryMemoryStore(ttl_seconds=3600), enabled=True))
    report = service.create_report(
        ReportCreate(report_type="investment_memo", prompt="Analyze NVDA", ticker="NVDA"),
        user_id="usr_test",
    )

    assert report.disclaimer
    assert report.evidence_count >= 0
    assert any("decision support" in section.content.lower() for section in report.sections)


def test_scenario_includes_assumptions_and_limitations() -> None:
    service = ScenariosService()
    scenario = service.create_scenario(
        ScenarioCreate(scenario_type="rebalance", assumptions=["equal weight"], title="Rebalance test"),
        user_id="usr_test",
    )

    assert scenario.assumptions
    assert scenario.limitations
    assert scenario.disclaimer
    assert scenario.approval_required is True
