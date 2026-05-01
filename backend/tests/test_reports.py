from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

from alphalens.api import deps
from alphalens.core.config import Settings
from alphalens.memory.in_memory import InMemoryMemoryStore
from alphalens.memory.service import MemoryService
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
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
    response = chat.chat(
        ChatRequest(messages=[ChatMessage(role=ChatRole.USER, content="Give me a portfolio update")])
    )
    service = ReportsService(memory_service=memory)
    report = service.create_report(
        ReportCreate(
            report_type="portfolio_update",
            prompt="Summarize latest portfolio changes",
            conversation_id=response.conversation_id,
            source_response_id=response.response_id,
        ),
        user_id="usr_reports_memory",
    )
    assert report.sections[0].key == "disclaimer"
    assert isinstance(report.citations, list)
