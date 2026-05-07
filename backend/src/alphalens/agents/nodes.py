"""LangGraph nodes for the AlphaLens agent.

Pipeline:

    interpret -> gather -> synthesize -> decide

Each node is a pure function over `AgentState`. Tools are looked up by
name in the `ToolRegistry`; the registry is injected into nodes via
factory functions so tests can inject fakes.

Intent classification and reasoning synthesis are delegated to
`LLMService`, which uses OpenAI when configured and a deterministic
keyword fallback otherwise. Tools are NEVER executed by the LLM —
`gather` always runs them deterministically based on classification
hints.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from alphalens.agents.state import AgentState
from alphalens.infrastructure.observability.langsmith import trace_node, trace_tool_call
from alphalens.integrations.llm.fallback_client import needs_rag_explicitly, needs_web_search
from alphalens.services.llm_service import LLMService
from alphalens.tools.policy import POLICY
from alphalens.tools.registry import ToolRegistry, ToolResult

NodeFn = Callable[[AgentState], AgentState]

_MACRO_KEYWORDS = frozenset(
    {
        "rates",
        "interest",
        "inflation",
        "cpi",
        "unemployment",
        "gdp",
        "macro",
        "recession",
        "fed",
        "federal reserve",
        "economy",
        "liquidity",
        "monetary",
        "fiscal",
        "yield",
        "treasury",
    }
)

_SEC_KEYWORDS = frozenset(
    {
        "sec",
        "10-k",
        "10k",
        "10-q",
        "10q",
        "filing",
        "annual report",
        "quarterly report",
        "risk factors",
        "risk factor",
        "fundamentals",
        "company risks",
        "business description",
        "management discussion",
        "mda",
        "earnings report",
        "edgar",
    }
)


def _needs_sec(text: str, intent: str, tickers: list[str]) -> bool:
    """Return True when SEC filing context is warranted.

    Triggers when:
    - The message contains SEC/filing-specific keywords, OR
    - Intent is research or trade_idea and a ticker is explicitly present
      (the agent then needs fundamental filing context).
    """
    lower = text.lower()
    if any(kw in lower for kw in _SEC_KEYWORDS):
        return True
    return intent in {"sec_filings_question", "investment_recommendation"} and bool(tickers)


def _needs_macro(text: str, intent: str) -> bool:
    """Return True when the message contains macro-relevant keywords.

    Triggers on any macro keyword regardless of intent, to also catch
    direct macro questions ("what is the Fed rate?") that the deterministic
    classifier labels as "general".
    """
    del intent
    lower = text.lower()
    return any(kw in lower for kw in _MACRO_KEYWORDS)


def _last_user_message(state: AgentState) -> str:
    for m in reversed(state.get("messages", [])):
        if m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


def _conversation_text(state: AgentState, *, max_messages: int = 6) -> str:
    """Return a compact multi-turn context string for intent classification.

    The last user message still drives the turn, but including a short trailing
    window lets follow-up questions inherit prior ticker / intent context.
    """
    history = state.get("messages", [])[-max_messages:]
    parts: list[str] = []
    for message in history:
        role = str(message.get("role", "unknown")).upper()
        content = str(message.get("content", "")).strip()
        if content:
            parts.append(f"{role}: {content}")
    return "\n".join(parts)


# 1. Interpret -----------------------------------------------------------------


def make_interpret_node(llm: LLMService) -> NodeFn:
    """Classify the user message into an intent + tool-selection hints."""

    def interpret(state: AgentState) -> AgentState:
        text = _last_user_message(state)
        conversation_text = _conversation_text(state)
        meta = {"input": text, "conversation_id": state.get("conversation_id")}
        with trace_node(
            "interpret",
            inputs={"message": text, "history_size": len(state.get("messages", []))},
            metadata=meta,
        ):
            classification = llm.classify_intent(message=conversation_text or text)
            rag_requested = needs_rag_explicitly(text, classification.intent)
            tickers = list(classification.tickers)
            output: AgentState = {
                "detected_language": state.get("detected_language"),
                "intent": classification.intent,
                "tickers": tickers,
                "needs_market_data": classification.needs_market_data,
                "needs_rag": classification.needs_rag or rag_requested,
                "rag_requested": rag_requested,
                "needs_portfolio": classification.needs_portfolio,
                "needs_risk_check": classification.needs_risk_check,
                # OR-merge LLM hint with the keyword heuristic so behaviour is
                # consistent whether or not OpenAI is configured.
                "needs_web_search": (
                    classification.needs_web_search
                    or needs_web_search(text, classification.intent)
                ),
                "needs_macro": _needs_macro(text, classification.intent),
                "needs_sec": _needs_sec(text, classification.intent, tickers),
                "evidence": [],
                "reasoning": [],
                "used_tools": [],
                "citations": [],
            }
        return output

    return interpret


# 2. Gather --------------------------------------------------------------------


def make_gather_node(registry: ToolRegistry) -> NodeFn:
    """Run tools indicated by classification hints (deterministic execution)."""

    def gather(state: AgentState) -> AgentState:
        tickers = state.get("tickers", [])
        needs_portfolio = state.get("needs_portfolio", False)
        needs_risk_check = state.get("needs_risk_check", False)
        needs_market_data = state.get("needs_market_data", False)
        needs_rag = state.get("needs_rag", False)
        needs_web = state.get("needs_web_search", False)
        needs_macro_data = state.get("needs_macro", False)
        needs_sec_data = state.get("needs_sec", False)

        evidence: list[dict] = []
        used: list[str] = []
        citations: list[dict] = []

        tool_meta = {
            "conversation_id": state.get("conversation_id"),
            "intent": state.get("intent"),
            "tickers": tickers,
        }

        def _run(name: str, **kwargs: Any) -> None:
            if not registry.has(name):
                return
            trace_tool_call(name, inputs=kwargs, metadata=tool_meta)
            try:
                result = registry.call(name, **kwargs)
            except Exception as exc:
                evidence.append(
                    {
                        "tool": name,
                        "summary": f"Tool '{name}' failed: {exc}",
                        "data": None,
                    }
                )
                used.append(name)
                return
            evidence.append(_to_evidence(result))
            used.append(name)
            if name == "rag_retrieve":
                citations.extend(_citations_from(result))

        node_inputs = {
            "intent": state.get("intent"),
            "tickers": tickers,
            "needs_portfolio": needs_portfolio,
            "needs_risk_check": needs_risk_check,
            "needs_market_data": needs_market_data,
            "needs_rag": needs_rag,
            "needs_web_search": needs_web,
            "needs_macro": needs_macro_data,
            "needs_sec": needs_sec_data,
        }
        with trace_node(
            "gather",
            inputs=node_inputs,
            metadata={"conversation_id": state.get("conversation_id")},
        ):
            if state.get("intent") in {"policy_breach_check", "rag_policy_question", "investment_recommendation", "risk_check"}:
                evidence.append(
                    {
                        "tool": "policy_rules",
                        "summary": (
                            "Applied IPS thresholds: single-name max 15%, trim threshold 12%, "
                            "sector caps from policy matrix."
                        ),
                        "data": {
                            "single_name_max": POLICY.single_name_max_weight,
                            "single_name_trim_threshold": POLICY.single_name_trim_threshold,
                            "sector_limits": POLICY.sector_max_weight,
                        },
                    }
                )
                used.append("policy_rules")
            if needs_portfolio:
                _run("portfolio_analyze")
            if needs_risk_check:
                _run("risk_check")
            if needs_market_data:
                _run("market_quote", tickers=tickers or _default_tickers())
            if needs_macro_data:
                _run("macro_snapshot")
            if needs_sec_data:
                for ticker in (tickers or _default_tickers()):
                    _run("sec_filings", ticker=ticker)
            if needs_rag:
                _run("rag_retrieve", query=_last_user_message(state))
            if needs_web:
                # Web search complements RAG with fresh external context;
                # never replaces it.
                _run("web_search", query=_last_user_message(state))

        return {
            "evidence": evidence,
            "used_tools": used,
            "citations": citations,
        }

    return gather


def _to_evidence(result: ToolResult) -> dict:
    return {"tool": result.name, "summary": result.summary, "data": result.data}


def _citations_from(result: ToolResult) -> list[dict]:
    chunks = (result.data or {}).get("chunks", []) if isinstance(result.data, dict) else []
    return [
        {
            "source_id": c.get("chunk_id", ""),
            "title": c.get("source", "kb"),
            "snippet": (c.get("text") or "")[:160],
            "score": c.get("score"),
        }
        for c in chunks
    ]


def _default_tickers() -> list[str]:
    return ["NVDA", "MSFT", "AAPL"]


# 3. Synthesize ----------------------------------------------------------------


def make_synthesize_node(llm: LLMService) -> NodeFn:
    """Build a reasoning trace from tool evidence using the LLM service."""

    def synthesize(state: AgentState) -> AgentState:
        intent = state.get("intent", "general")
        deterministic = _baseline_reasoning(state)
        meta = {
            "conversation_id": state.get("conversation_id"),
            "intent": intent,
            "tickers": state.get("tickers", []),
        }
        with trace_node(
            "synthesize",
            inputs={"intent": intent, "evidence_count": len(state.get("evidence", []))},
            metadata=meta,
        ):
            synthesis = llm.synthesize_decision(
                intent=intent,
                recommendation="",  # not yet decided; decide_node runs after.
                evidence=list(state.get("evidence", [])),
                deterministic_reasoning=deterministic,
            )
            # Always keep at least the deterministic baseline if the LLM returned
            # an empty reasoning list — never lose information.
            reasoning = synthesis.reasoning or deterministic
        return {"reasoning": reasoning}

    return synthesize


def _baseline_reasoning(state: AgentState) -> list[str]:
    intent = state.get("intent", "general")
    reasoning = [f"Interpreted intent as '{intent}'."]
    for ev in state.get("evidence", []):
        reasoning.append(f"[{ev['tool']}] {ev['summary']}")
    return reasoning


# 4. Decide --------------------------------------------------------------------


def decide_node(state: AgentState) -> AgentState:
    """Produce a recommendation and `requires_approval` flag.

    Rules:
    - Any risk violation -> escalate, requires_approval.
    - Risk warning on a position -> trim that position.
    - Trade-idea intent without violations -> buy/inform with approval flag.
    - Otherwise -> inform.
    """

    intent = state.get("intent", "general")
    meta = {
        "conversation_id": state.get("conversation_id"),
        "intent": intent,
        "tickers": state.get("tickers", []),
    }
    with trace_node(
        "decide",
        inputs={"intent": intent, "used_tools": state.get("used_tools", [])},
        metadata=meta,
    ):
        risk_data = _evidence_data(state, "risk_check") or {}
        status = risk_data.get("status", "clean")
        findings = risk_data.get("findings", [])

        requires_approval = False
        reasoning_extra: list[str] = []

        if status == "violations" and intent in {"policy_breach_check", "risk_review", "investment_recommendation", "risk_check", "trade_idea"}:
            recommendation = "escalate"
            requires_approval = True
            risk_level = "high"
            confidence = 0.85
            reasoning_extra.append(
                "Policy violation detected; escalating for committee review."
            )
        elif status == "warnings" and any(
            f.get("code") == "single_name_trim" for f in findings
        ) and intent in {"investment_recommendation", "trade_idea"}:
            recommendation = "trim"
            requires_approval = True
            risk_level = "medium"
            confidence = 0.75
            offenders = [f["subject"] for f in findings if f.get("code") == "single_name_trim"]
            reasoning_extra.append(
                f"Recommend trimming {', '.join(offenders)} above policy trim threshold."
            )
        elif intent in {"investment_recommendation", "trade_idea"}:
            recommendation = "buy"
            requires_approval = True
            # Trade idea without a full risk picture: surface lower confidence so
            # reviewers know the recommendation is preliminary.
            risk_level = "medium"
            confidence = 0.65
            reasoning_extra.append(
                "Trade idea detected; human approval required per IPS section 7."
            )
        elif intent in {"risk_review", "policy_breach_check", "risk_check"}:
            recommendation = "hold"
            risk_level = "low"
            confidence = 0.7
            reasoning_extra.append("No policy breaches; current allocation is within limits.")
        elif intent in {"portfolio_performance", "portfolio_review"}:
            recommendation = "inform"
            risk_level = "low"
            confidence = 0.78 if intent == "portfolio_performance" else 0.7
            reasoning_extra.append("Performance request detected; prioritizing factual portfolio outcomes.")
        elif intent in {"rag_policy_question", "market_news_question", "sec_filings_question", "macro_question", "general_question"}:
            recommendation = "inform"
            risk_level = "low"
            confidence = 0.7
        else:
            recommendation = "inform"
            risk_level = "low"
            confidence = 0.7

        # Tool failures or unclear tool results should never look fully confident:
        # bump risk to medium and cap confidence at 0.6 unless we already escalated.
        if recommendation != "escalate" and _has_tool_failure(state):
            risk_level = "medium" if risk_level == "low" else risk_level
            confidence = min(confidence, 0.6)
            reasoning_extra.append("One or more tools failed; downgrading confidence.")

        answer = _format_answer(intent, recommendation, reasoning_extra, state)

    return {
        "recommendation": recommendation,
        "requires_approval": requires_approval,
        "risk_level": risk_level,
        "confidence": confidence,
        "reasoning": [*state.get("reasoning", []), *reasoning_extra],
        "answer": answer,
    }


def _has_tool_failure(state: AgentState) -> bool:
    for ev in state.get("evidence", []):
        if ev.get("data") is None and "failed" in str(ev.get("summary", "")).lower():
            return True
    return False


def _evidence_data(state: AgentState, tool: str) -> dict | None:
    for ev in state.get("evidence", []):
        if ev.get("tool") == tool:
            data = ev.get("data")
            if isinstance(data, dict):
                return data
    return None


def _format_answer(
    intent: str,
    recommendation: str,
    extras: list[str],
    state: AgentState,
) -> str:
    if intent == "portfolio_performance":
        return _format_performance_answer(state, extras)
    if intent == "portfolio_review":
        return _format_generic_evidence_answer("Portfolio review", state, extras)
    if intent == "policy_breach_check":
        return _format_policy_breach_answer(state, extras)
    if intent == "risk_check":
        return _format_policy_breach_answer(state, extras)
    if intent == "rag_policy_question":
        return _format_rag_policy_answer(state, extras)
    if intent == "research":
        return _format_rag_policy_answer(state, extras)
    if intent == "investment_recommendation":
        return _format_investment_recommendation_answer(state, recommendation, extras)
    if intent == "trade_idea":
        return _format_investment_recommendation_answer(state, recommendation, extras)
    if intent == "market_news_question":
        return _format_generic_evidence_answer("Market and news summary", state, extras)
    if intent == "market_news":
        return _format_generic_evidence_answer("Market and news summary", state, extras)
    if intent == "sec_filings_question":
        return _format_generic_evidence_answer("SEC filings summary", state, extras)
    if intent == "macro_question":
        return _format_generic_evidence_answer("Macro overview", state, extras)
    if intent == "risk_review":
        return _format_generic_evidence_answer("Risk review", state, extras)

    language = state.get("response_language")
    if language == "de":
        head = f"Absicht: {intent}. Empfehlung: {recommendation}."
        body = " ".join(extras) if extras else "Zusammenfassung basierend auf den verfügbaren Belegen."
        tools = state.get("used_tools", [])
        tail = f" Verwendete Werkzeuge: {', '.join(tools)}." if tools else ""
        return f"{head} {body}{tail}".strip()
    if language == "fr":
        head = f"Intention: {intent}. Recommandation: {recommendation}."
        body = " ".join(extras) if extras else "Résumé basé sur les éléments disponibles."
        tools = state.get("used_tools", [])
        tail = f" Outils consultés : {', '.join(tools)}." if tools else ""
        return f"{head} {body}{tail}".strip()
    if language == "ar":
        head = f"النية: {intent}. التوصية: {recommendation}."
        body = " ".join(extras) if extras else "ملخص بناءً على الأدلة المتاحة."
        tools = state.get("used_tools", [])
        tail = f" الأدوات المستخدمة: {', '.join(tools)}." if tools else ""
        return f"{head} {body}{tail}".strip()
    head = f"Intent: {intent}. Recommendation: {recommendation}."
    body = " ".join(extras) if extras else "Summary based on available evidence."
    tools = state.get("used_tools", [])
    tail = f" Tools consulted: {', '.join(tools)}." if tools else ""
    return f"{head} {body}{tail}".strip()


def _format_policy_breach_answer(state: AgentState, extras: list[str]) -> str:
    risk_data = _evidence_data(state, "risk_check") or {}
    findings = risk_data.get("findings") or []
    if not isinstance(findings, list):
        findings = []
    lines = ["Policy breach check:"]
    if findings:
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            subject = str(finding.get("subject", "Portfolio"))
            message = str(finding.get("message", "Threshold condition detected"))
            severity = str(finding.get("severity", "medium"))
            observed = finding.get("observed")
            limit = finding.get("limit")
            if isinstance(observed, (int, float)) and isinstance(limit, (int, float)):
                lines.append(
                    f"- {subject}: {message} | threshold {float(limit) * 100:.2f}% vs current {float(observed) * 100:.2f}% | severity: {severity}"
                )
            else:
                lines.append(f"- {subject}: {message} (severity: {severity})")
    else:
        lines.append("- No active policy breaches detected in current snapshot.")
    lines.append("- Approval implication: recommendations that trim, rebalance, buy, or sell require committee approval.")
    lines.append("- Suggested next review step: validate the flagged positions and route any trade action to approvals.")
    if extras:
        lines.append(f"- Notes: {' '.join(extras)}")
    return "\n".join(lines)


def _format_rag_policy_answer(state: AgentState, extras: list[str]) -> str:
    rag_data = _evidence_data(state, "rag_retrieve") or {}
    chunks = rag_data.get("chunks") if isinstance(rag_data, dict) else []
    lines = ["Policy summary from knowledge base:"]
    if isinstance(chunks, list) and chunks:
        for chunk in chunks[:4]:
            if not isinstance(chunk, dict):
                continue
            source = str(chunk.get("source", "knowledge_base"))
            text = str(chunk.get("text", "")).strip().replace("\n", " ")
            snippet = text[:180] + ("..." if len(text) > 180 else "")
            lines.append(f"- {source}: {snippet}")
    else:
        lines.append("- No policy chunks were retrieved for this question.")
        lines.append(
            f"- Structured fallback: single-name max {POLICY.single_name_max_weight * 100:.0f}%, trim threshold {POLICY.single_name_trim_threshold * 100:.0f}%."
        )
    if extras:
        lines.append(f"- Notes: {' '.join(extras)}")
    return "\n".join(lines)


def _format_investment_recommendation_answer(
    state: AgentState,
    recommendation: str,
    extras: list[str],
) -> str:
    tickers = state.get("tickers", []) or _default_tickers()
    lines = [f"Investment recommendation: {recommendation}."]
    lines.append(f"- Evaluated symbols: {', '.join(tickers)}")
    portfolio = _evidence_data(state, "portfolio_analyze") or {}
    positions = portfolio.get("positions") if isinstance(portfolio, dict) else []
    nvda_position = None
    if isinstance(positions, list):
        for item in positions:
            if isinstance(item, dict) and str(item.get("symbol", "")).upper() == "NVDA":
                nvda_position = item
                break
    if isinstance(nvda_position, dict):
        weight = nvda_position.get("weight")
        if isinstance(weight, (int, float)):
            lines.append(f"- NVDA current weight: {float(weight) * 100:.2f}%")
    lines.append(f"- Policy trim threshold: {POLICY.single_name_trim_threshold * 100:.2f}%")
    rag_data = _evidence_data(state, "rag_retrieve") or {}
    chunks = rag_data.get("chunks") if isinstance(rag_data, dict) else []
    if isinstance(chunks, list) and chunks:
        lines.append("- Internal policy context was included from the knowledge base.")
        for chunk in chunks[:3]:
            if not isinstance(chunk, dict):
                continue
            source = str(chunk.get("source", "knowledge_base"))
            snippet = str(chunk.get("text", "")).replace("\n", " ").strip()[:140]
            lines.append(f"- Evidence: {source} -> {snippet}")
    else:
        lines.append("- Internal policy context not retrieved; recommendation is based on non-RAG evidence.")
    lines.append("- Approval requirement: committee approval is required before execution actions.")
    lines.append("- Limitations: this recommendation is based on synthetic/demo holdings unless live providers are configured.")
    if extras:
        lines.append(f"- Risk notes: {' '.join(extras)}")
    return "\n".join(lines)


def _format_generic_evidence_answer(
    title: str,
    state: AgentState,
    extras: list[str],
) -> str:
    lines = [f"{title}:"]
    if state.get("used_tools"):
        lines.append(f"- Tools consulted: {', '.join(state['used_tools'])}")
    else:
        lines.append("- No external tools were required for this answer.")
    if extras:
        lines.append(f"- Notes: {' '.join(extras)}")
    return "\n".join(lines)


def _format_performance_answer(state: AgentState, extras: list[str]) -> str:
    portfolio = _evidence_data(state, "portfolio_analyze") or {}
    total_value = portfolio.get("total_value")
    estimated_return = portfolio.get("estimated_one_month_return")
    day_pnl = portfolio.get("estimated_day_pnl")
    top = portfolio.get("top_contributors") or []
    laggards = portfolio.get("laggards") or []

    lines = ["Portfolio performance snapshot (demo data):"]
    if isinstance(total_value, (int, float)):
        lines.append(f"- Current NAV: ${float(total_value):,.0f}")
    if isinstance(estimated_return, (int, float)):
        lines.append(f"- Estimated 1M return: {float(estimated_return) * 100:.2f}%")
    elif isinstance(day_pnl, (int, float)):
        lines.append(f"- Day P&L proxy: ${float(day_pnl):,.0f}")
    else:
        lines.append("- 1M return and day P&L are unavailable in the current synthetic snapshot.")

    if top:
        top_text = ", ".join(
            f"{item.get('symbol', 'N/A')} ({float(item.get('return', 0.0)) * 100:.2f}%)"
            for item in top[:3]
        )
        lines.append(f"- Top contributors: {top_text}")
    if laggards:
        lag_text = ", ".join(
            f"{item.get('symbol', 'N/A')} ({float(item.get('return', 0.0)) * 100:.2f}%)"
            for item in laggards[:3]
        )
        lines.append(f"- Laggards: {lag_text}")

    lines.append("- Benchmark comparison unavailable unless external market provider is configured.")
    lines.append("- Limitations: values are derived from synthetic/demo holdings.")
    if extras:
        lines.append(f"- Risk notes: {' '.join(extras)}")
    return "\n".join(lines)
