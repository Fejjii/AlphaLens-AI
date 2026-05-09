"""LangGraph agent state.

The state is intentionally schema-light (TypedDict) to interop with
LangGraph reducers. Strong contracts live at the API boundary in
`alphalens.schemas.agent`.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    conversation_id: str
    messages: list[dict[str, Any]]
    conversation_history: list[dict[str, Any]]
    previous_decisions: list[dict[str, Any]]
    response_language: str
    router_answer_type: str
    router_intent: str
    router_confidence: float
    router_reason: str
    router_suggested_tools: list[str]
    router_language: str

    intent: str
    tickers: list[str]
    needs_market_data: bool
    needs_rag: bool
    rag_requested: bool
    needs_portfolio: bool
    needs_risk_check: bool
    needs_web_search: bool
    needs_macro: bool
    needs_sec: bool

    evidence: list[dict[str, Any]]
    reasoning: list[str]
    used_tools: list[str]
    citations: list[dict[str, Any]]

    recommendation: str
    requires_approval: bool
    risk_level: str
    confidence: float
    answer: str
    tool_limitations: list[str]
    graph_input_suggested_tools: list[str]
    gather_selected_tools_before: list[str]
    gather_selected_tools_after: list[str]
    tools_executed: list[str]
    tools_skipped: list[str]
    skip_reasons: list[str]
