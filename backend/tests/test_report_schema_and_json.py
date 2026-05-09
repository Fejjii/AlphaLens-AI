from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import create_engine, inspect, text

from alphalens.core.json_safe import to_json_safe
from alphalens.infrastructure.schema_guards import ensure_dev_report_table_schema
from alphalens.repositories.reports import _to_model
from alphalens.schemas.agent import EvidenceItem
from alphalens.schemas.report import (
    ReportGenerationMeta,
    ReportResponse,
    ReportSection,
    ReportStatus,
    ReportType,
)


class _SampleEnum(str, Enum):
    HOLD = "hold"


def test_to_json_safe_coerces_enum_datetime_and_nested() -> None:
    raw = {
        "nested": {"e": _SampleEnum.HOLD, "d": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)},
        "s": {1, 2},
    }
    out = to_json_safe(raw)
    assert out["nested"]["e"] == "hold"
    assert "2026-01-02" in str(out["nested"]["d"])
    assert sorted(out["s"]) == [1, 2]


def test_ensure_dev_report_table_schema_adds_memo_metadata_sqlite(tmp_path) -> None:
    db = tmp_path / "legacy_reports.db"
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE reports (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    report_type VARCHAR(32) NOT NULL,
                    conversation_id VARCHAR(64),
                    source_response_id VARCHAR(64),
                    ticker VARCHAR(16),
                    status VARCHAR(32) NOT NULL,
                    sections TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    citations TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
    ensure_dev_report_table_schema(engine, app_env="dev")
    cols = {c["name"] for c in inspect(engine).get_columns("reports")}
    assert "memo_metadata" in cols


def test_ensure_dev_report_table_schema_skips_prod() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE reports (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    report_type VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    sections TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    citations TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
    ensure_dev_report_table_schema(engine, app_env="prod")
    cols = {c["name"] for c in inspect(engine).get_columns("reports")}
    assert "memo_metadata" not in cols


def test_report_repository_to_model_sanitizes_evidence_payload() -> None:
    now = datetime.now(tz=UTC)
    report = ReportResponse(
        id="rpt_test_json_safe",
        user_id="usr_x",
        title="Memo",
        report_type=ReportType.INVESTMENT_MEMO,
        status=ReportStatus.GENERATED,
        sections=[ReportSection(key="executive_summary", title="Summary", content="Hello")],
        evidence=[
            EvidenceItem(
                tool="t",
                summary="s",
                data={"e": _SampleEnum.HOLD, "ts": now},
            )
        ],
        memo_metadata=ReportGenerationMeta(rag_sources_count=1),
    )
    model = _to_model(report)
    assert isinstance(model.evidence[0]["data"], dict)
    assert model.evidence[0]["data"]["e"] == "hold"
    assert "ts" in model.evidence[0]["data"]


async def test_memo_portfolio_performance_chatpanel_like_payload(
    client,
    auth_headers: dict[str, str],
) -> None:
    """Mirrors frontend buildInvestmentMemoReportPayload for 1M portfolio performance."""
    payload = {
        "report_type": "investment_memo",
        "conversation_id": "conv_chatpanel_perf",
        "source_response_id": "msg_src_perf_001",
        "ticker": None,
        "prompt": "Generate an investment memo from this agent decision.",
        "memo_context": {
            "user_prompt": "What has been the performance of the portfolio in the last 1 month?",
            "agent_final_answer": (
                "Over the last month the portfolio returned +2.1% with contributors MSFT and NVDA; "
                "drawdown was limited versus the benchmark."
            ),
            "answer_type": "investment_decision",
            "decision": {
                "action": "inform",
                "recommendation": "inform",
                "risk_level": "low",
                "confidence": 0.82,
                "approval_required": False,
                "key_reasoning": ["Positive 1M return; concentration unchanged within IPS."],
                "key_evidence": [
                    {
                        "tool": "portfolio_analyze",
                        "summary": "1M return +2.1%; top contributors MSFT, NVDA.",
                        "data": {"period": "1m"},
                    }
                ],
                "policy_flags": [],
            },
            "analysis": {
                "intent": "portfolio_performance",
                "tools_used": ["portfolio_analyze", "market_quote"],
                "rag_sources": [],
                "provider_modes": [],
                "data_used": ["nav", "returns", "contributors"],
                "limitations": [],
                "orchestration_trace": {},
                "portfolio_snapshot_used": "synthetic_portfolio_holdings.csv",
                "policy_rules_used": [],
            },
            "ticker_or_subject": "Portfolio",
        },
    }
    response = await client.post("/reports", json=payload, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["memo_metadata"]["limited_context"] is False
    assert body["memo_metadata"]["rag_sources_count"] == 0
    text_blob = " ".join(s["content"] for s in body["sections"]).lower()
    assert "portfolio" in text_blob
    assert ("2.1%" in text_blob) or ("return" in text_blob) or ("month" in text_blob)


async def test_memo_accepts_malformed_rag_and_tools(client, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/reports",
        json={
            "report_type": "investment_memo",
            "prompt": "Memo with messy analysis shapes",
            "ticker": "NVDA",
            "memo_context": {
                "agent_final_answer": "NVDA trim review.",
                "decision": {
                    "recommendation": "trim",
                    "key_evidence": {"tool": "rag_retrieve", "summary": "single dict evidence"},
                },
                "analysis": {
                    "tools_used": "portfolio_analyze",
                    "rag_sources": "not a list",
                },
            },
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    meta = response.json()["memo_metadata"]
    assert meta["rag_sources_count"] >= 1
