from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

from alphalens.api import deps
from alphalens.core.config import Settings
from alphalens.memory.in_memory import InMemoryMemoryStore
from alphalens.memory.service import MemoryService
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.schemas.user import UserPlan, UserProfile, UserRole
from alphalens.schemas.report import ReportCreate
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.rag_service import RAGService
from alphalens.services.reports_service import ReportsService
from alphalens.tools.registry import ToolRegistry


def _build_chat_service(*, tmp_path: Path, memory_service: MemoryService) -> ChatService:
    settings = Settings(
        knowledge_base_path=str(tmp_path / "kb"),
        rag_collection=f"reports_test_{tmp_path.name}",
    )
    kb_dir = Path(settings.knowledge_base_path)
    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "note.md").write_text("# Note\n\nReport test fixture.\n", encoding="utf-8")
    return ChatService(
        settings=settings,
        rag_service=RAGService(settings),
        approvals_service=ApprovalsService(),
        registry=ToolRegistry(),
        memory_service=memory_service,
    )


async def test_reports_api_create_list_get(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/reports",
        json={
            "report_type": "investment_memo",
            "prompt": "Should we increase NVDA exposure?",
            "ticker": "NVDA",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"].startswith("rpt_")
    assert body["status"] == "generated"
    assert len(body["sections"]) >= 8
    assert "memo_metadata" in body

    list_response = await client.get("/reports", headers=auth_headers)
    assert list_response.status_code == 200
    reports = list_response.json()
    assert len(reports) == 1

    report_id = body["id"]
    get_response = await client.get(f"/reports/{report_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == report_id

    usage_events = deps.get_usage_service().list_usage_events()
    assert any(event.event_type == "report_generated" for event in usage_events)


async def test_report_summary_endpoint(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await client.post(
        "/reports",
        json={"report_type": "investment_memo", "prompt": "Evaluate AAPL", "ticker": "AAPL"},
        headers=auth_headers,
    )
    await client.post(
        "/reports",
        json={"report_type": "risk_review", "prompt": "Review concentration risk"},
        headers=auth_headers,
    )
    response = await client.get("/reports/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_reports"] == 2
    assert body["generated_reports"] == 2
    assert body["by_type"]["investment_memo"] == 1
    assert body["by_type"]["risk_review"] == 1


def test_report_service_uses_memory_evidence(tmp_path: Path) -> None:
    memory = MemoryService(store=InMemoryMemoryStore(ttl_seconds=3600), enabled=True)
    chat = _build_chat_service(tmp_path=tmp_path, memory_service=memory)
    user = UserProfile(
        id="usr_reports_memory",
        email="reports.mem@example.com",
        full_name="Reports Memory User",
        role=UserRole.USER,
        plan=UserPlan.FREE,
        is_active=True,
    )
    response = chat.chat(
        ChatRequest(messages=[ChatMessage(role=ChatRole.USER, content="Give me a portfolio update")]),
        user=user,
    )
    service = ReportsService(memory_service=memory)
    report = service.create_report(
        ReportCreate(
            report_type="portfolio_update",
            prompt="Summarize latest portfolio changes",
            conversation_id=response.conversation_id,
            source_response_id=response.response_id,
        ),
        user_id=user.id,
    )
    keys = {section.key for section in report.sections}
    assert "disclaimer" in keys
    assert isinstance(report.citations, list)


async def test_memo_from_nvda_rag_decision_is_context_specific(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    chat = await client.post(
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
    assert chat.status_code == 200
    answer = chat.json()
    payload = {
        "report_type": "investment_memo",
        "conversation_id": answer["conversation_id"],
        "source_response_id": answer["response_id"],
        "ticker": "NVDA",
        "prompt": "Generate memo from source decision",
        "memo_context": {
            "agent_final_answer": answer["analysis"]["final_answer"],
            "answer_type": answer["answer_type"],
            "decision": {
                "action": answer["decision"]["recommendation"],
                "recommendation": answer["decision"]["recommendation"],
                "risk_level": answer["decision"]["risk_level"],
                "confidence": answer["decision"]["confidence"],
                "approval_required": answer["decision"]["requires_approval"],
                "approval_id": answer["decision"]["approval_id"],
                "approval_required_reason": answer["decision"]["approval_required_reason"],
                "key_reasoning": answer["decision"]["reasoning"],
                "key_evidence": answer["decision"]["evidence"],
                "policy_flags": answer["decision"].get("policy_flags", []),
            },
            "analysis": {
                "intent": answer["analysis"]["intent"],
                "tools_used": answer["analysis"]["tools_used"],
                "rag_sources": answer["analysis"]["rag_sources"],
                "provider_modes": answer["analysis"]["provider_modes"],
                "data_used": answer["analysis"]["data_used"],
                "limitations": answer["analysis"]["limitations"],
                "orchestration_trace": answer["analysis"]["orchestration_trace"],
                "portfolio_snapshot_used": answer["analysis"]["portfolio_snapshot_used"],
                "policy_rules_used": answer["analysis"]["policy_rules_used"],
            },
            "ticker_or_subject": "NVDA",
        },
    }
    report = await client.post("/reports", json=payload, headers=auth_headers)
    assert report.status_code == 200
    body = report.json()
    whole = " ".join([s["content"] + " " + " ".join(s["bullets"]) for s in body["sections"]]).lower()
    assert "nvda" in whole
    assert ("trim" in whole) or ("review" in whole)
    assert ("threshold" in whole) or ("concentration" in whole)
    assert ("internal policy" in whole) or ("knowledge base" in whole)
    assert ("approval" in whole) or ("human" in whole)


async def test_memo_from_performance_decision_differs_from_nvda(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    r_nvda = await client.post(
        "/reports",
        json={
            "report_type": "investment_memo",
            "ticker": "NVDA",
            "prompt": "Generate memo for NVDA trim review",
            "memo_context": {
                "answer_type": "investment_decision",
                "agent_final_answer": "NVDA should be reviewed for trimming above policy thresholds.",
                "decision": {
                    "recommendation": "trim",
                    "risk_level": "medium",
                    "confidence": 0.75,
                    "approval_required": True,
                    "key_reasoning": ["NVDA weight exceeds trim threshold."],
                    "key_evidence": [{"tool": "policy_rules", "summary": "Single-name trim threshold applies."}],
                },
                "analysis": {
                    "intent": "investment_recommendation",
                    "tools_used": ["policy_rules", "portfolio_analyze", "rag_retrieve"],
                    "rag_sources": [{"document_title": "portfolio_committee_notes", "chunk_id": "c1", "score": 0.9, "snippet": "trim review guidance", "source": "portfolio_committee_notes.md"}],
                    "provider_modes": [],
                    "data_used": ["policy docs", "portfolio snapshot"],
                    "limitations": [],
                    "orchestration_trace": {},
                    "policy_rules_used": ["single_name_trim"],
                },
                "ticker_or_subject": "NVDA",
            },
        },
        headers=auth_headers,
    )
    assert r_nvda.status_code == 200
    r_perf = await client.post(
        "/reports",
        json={
            "report_type": "investment_memo",
            "ticker": "PORTFOLIO",
            "prompt": "Generate memo for monthly portfolio performance",
            "memo_context": {
                "answer_type": "investment_decision",
                "agent_final_answer": "Portfolio 1M return is positive with NVDA and MSFT as contributors.",
                "decision": {
                    "recommendation": "inform",
                    "risk_level": "low",
                    "confidence": 0.8,
                    "approval_required": False,
                    "key_reasoning": ["Performance snapshot shows positive 1M return."],
                    "key_evidence": [{"tool": "portfolio_analyze", "summary": "NAV and top contributors available."}],
                },
                "analysis": {
                    "intent": "portfolio_performance",
                    "tools_used": ["portfolio_analyze", "market_quote"],
                    "rag_sources": [],
                    "provider_modes": [],
                    "data_used": ["nav", "return", "contributors"],
                    "limitations": ["Market provider in fallback mode."],
                    "orchestration_trace": {},
                    "portfolio_snapshot_used": "synthetic_portfolio_holdings.csv",
                    "policy_rules_used": [],
                },
                "ticker_or_subject": "Portfolio",
            },
        },
        headers=auth_headers,
    )
    assert r_perf.status_code == 200
    nvda_body = r_nvda.json()
    perf_body = r_perf.json()
    nvda_text = " ".join(section["content"] for section in nvda_body["sections"]).lower()
    perf_text = " ".join(section["content"] for section in perf_body["sections"]).lower()
    assert nvda_text != perf_text
    assert "trim" in nvda_text
    assert "portfolio" in perf_text
    assert ("return" in perf_text) or ("nav" in perf_text) or ("p&l" in perf_text)


async def test_memo_accepts_full_chat_analysis_blob_extras_stripped(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Frontend sometimes forwards the full ChatAnalysis object; extras must not 422."""
    chat = await client.post(
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
    assert chat.status_code == 200
    answer = chat.json()
    analysis = dict(answer["analysis"])
    analysis["extra_field_should_be_ignored"] = "x"
    payload = {
        "report_type": "investment_memo",
        "conversation_id": answer["conversation_id"],
        "source_response_id": answer["response_id"],
        "ticker": "NVDA",
        "prompt": "Generate memo from source decision",
        "memo_context": {
            "agent_final_answer": answer["analysis"]["final_answer"],
            "answer_type": answer["answer_type"],
            "decision": answer["decision"],
            "analysis": analysis,
            "ticker_or_subject": "NVDA",
        },
    }
    report = await client.post("/reports", json=payload, headers=auth_headers)
    assert report.status_code == 200
    body = report.json()
    assert body["memo_metadata"]["rag_sources_count"] >= 0
    assert "nvda" in " ".join(s["content"] for s in body["sections"]).lower()


async def test_memo_succeeds_when_source_response_id_unknown_but_memo_context_present(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    report = await client.post(
        "/reports",
        json={
            "report_type": "investment_memo",
            "conversation_id": "conv_does_not_exist_123",
            "source_response_id": "msg_never_saved_999",
            "ticker": "NVDA",
            "prompt": "Generate memo from client context",
            "memo_context": {
                "user_prompt": "Should NVDA be trimmed per policy?",
                "agent_final_answer": "NVDA is above trim threshold; reduce pending approval.",
                "answer_type": "investment_decision",
                "decision": {
                    "recommendation": "trim",
                    "risk_level": "medium",
                    "confidence": 0.8,
                    "approval_required": True,
                    "approval_id": "appr_test_1",
                    "key_reasoning": ["Weight exceeds IPS trim review level."],
                    "key_evidence": [{"tool": "rag_retrieve", "summary": "Policy doc cites 12% trim review."}],
                    "policy_flags": ["concentration"],
                },
                "analysis": {
                    "intent": "rag_policy_question",
                    "tools_used": ["rag_retrieve", "portfolio_analyze"],
                    "rag_sources": [
                        {
                            "document_title": "IPS",
                            "chunk_id": "c1",
                            "score": 0.88,
                            "snippet": "Single-name trim threshold 12%.",
                            "source": "ips.md",
                        }
                    ],
                    "provider_modes": [],
                    "data_used": ["RAG"],
                    "limitations": ["Demo corpus."],
                    "orchestration_trace": {},
                    "portfolio_snapshot_used": "synthetic_portfolio_holdings.csv",
                    "policy_rules_used": ["single_name_trim"],
                },
                "ticker_or_subject": "NVDA",
            },
        },
        headers=auth_headers,
    )
    assert report.status_code == 200
    body = report.json()
    assert body["memo_metadata"]["source_lookup_failed"] is True
    assert body["memo_metadata"]["rag_sources_count"] == 1


async def test_memo_with_no_evidence_marks_limited_context(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/reports",
        json={"report_type": "investment_memo", "prompt": "Generate memo", "ticker": "NVDA"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["memo_metadata"]["limited_context"] is True
    text = " ".join([s["content"] for s in body["sections"]]).lower()
    assert "limited context" in text


