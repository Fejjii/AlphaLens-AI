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

import re
from collections.abc import Callable
from typing import Any

from alphalens.agents.state import AgentState
from alphalens.infrastructure.observability.langsmith import trace_node, trace_tool_call
from alphalens.integrations.llm.fallback_client import needs_rag_explicitly, needs_web_search
from alphalens.services.llm_service import LLMService
from alphalens.tools.policy import POLICY
from alphalens.tools.registry import ToolRegistry, ToolResult

NodeFn = Callable[[AgentState], AgentState]

_SCENARIO_SHOCK_DETECT_RE = re.compile(
    r"(what\s+if|what\s+happens\s+if|stress\s+scenario|scenario\s+analysis|price\s+shock|\bshock\b|"
    r"drops?\b|dropped\b|falls?\b|fell\b|declin(e|es|ed|ing)\b)",
    re.IGNORECASE,
)
_SHOCK_PCT_RE = re.compile(
    r"(?P<sign>-)?\s*(?P<num>\d+(?:\.\d+)?)\s*(?:%|percent)\b",
    re.IGNORECASE,
)
_TICKER_RE_NODES = re.compile(r"\b[A-Z]{2,5}\b")
_KNOWN_TICKERS_NODES: frozenset[str] = frozenset(
    {
        "NVDA",
        "MSFT",
        "AAPL",
        "TSM",
        "AVGO",
        "GOOGL",
        "AMZN",
        "META",
        "ASML",
        "CRM",
        "AMD",
        "SPY",
        "QQQ",
    }
)

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

_ROUTER_TOOL_ALIASES: dict[str, str] = {
    "portfolio": "portfolio_analyzer",
    "portfolio_analyzer": "portfolio_analyzer",
    "portfolio_analyze": "portfolio_analyzer",
    "policy_rules": "risk_checker",
    "policy": "risk_checker",
    "risk_checker": "risk_checker",
    "risk_check": "risk_checker",
    "rag": "rag_retriever",
    "rag_retriever": "rag_retriever",
    "rag_retrieve": "rag_retriever",
    "web_search": "web_news",
    "web_news": "web_news",
    "news": "web_news",
    "market": "market_data",
    "market_data": "market_data",
    "market_quote": "market_data",
    "macro": "macro_data",
    "macro_data": "macro_data",
    "macro_snapshot": "macro_data",
    "sec": "sec_filings",
    "sec_filings": "sec_filings",
    "scenario": "scenario_simulation",
    "scenario_simulation": "scenario_simulation",
}

_CANONICAL_TO_EXECUTABLE: dict[str, str] = {
    "portfolio_analyzer": "portfolio_analyze",
    "risk_checker": "risk_check",
    "rag_retriever": "rag_retrieve",
    "market_data": "market_quote",
    "web_news": "web_search",
    "macro_data": "macro_snapshot",
    "sec_filings": "sec_filings",
    "scenario_simulation": "scenario_simulation",
}


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


def _is_scenario_shock_question(text: str) -> bool:
    lowered = text.lower()
    if not _SCENARIO_SHOCK_DETECT_RE.search(lowered):
        return False
    if _SHOCK_PCT_RE.search(text):
        return True
    if "portfolio" in lowered:
        return True
    for match in _TICKER_RE_NODES.findall(text):
        if match in _KNOWN_TICKERS_NODES:
            return True
    return False


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
            if _is_scenario_shock_question(text):
                output["intent"] = "scenario_simulation"
                output["needs_portfolio"] = True
                output["needs_market_data"] = False
                output["needs_risk_check"] = False
                if not output.get("tickers"):
                    inferred = sorted(
                        {m for m in _TICKER_RE_NODES.findall(text) if m in _KNOWN_TICKERS_NODES}
                    )
                    if inferred:
                        output["tickers"] = inferred
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
        router_suggested = list(state.get("router_suggested_tools", []) or [])
        user_text = _last_user_message(state)

        evidence: list[dict] = []
        used: list[str] = []
        citations: list[dict] = []
        limitations: list[str] = []
        tools_skipped: list[str] = []
        skip_reasons: list[str] = []
        selected_before: list[str] = []
        selected_after: list[str] = []

        tool_meta = {
            "conversation_id": state.get("conversation_id"),
            "intent": state.get("intent"),
            "tickers": tickers,
        }

        def _run(name: str, **kwargs: Any) -> None:
            if not registry.has(name):
                tools_skipped.append(name)
                reason = f"Suggested tool {name} is not available in the current registry."
                skip_reasons.append(reason)
                limitations.append(reason)
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

        def _append_unique(seq: list[str], item: str) -> None:
            if item not in seq:
                seq.append(item)

        def _normalize_router_tools(raw_tools: list[str]) -> tuple[list[str], list[dict[str, str]]]:
            normalized: list[str] = []
            skipped: list[dict[str, str]] = []
            for raw in raw_tools:
                key = str(raw or "").strip().lower().replace(" ", "_")
                if not key:
                    continue
                canonical = _ROUTER_TOOL_ALIASES.get(key)
                if canonical is None:
                    skipped.append(
                        {
                            "tool": key,
                            "reason": "Router suggested unknown tool alias.",
                        }
                    )
                    continue
                if canonical not in normalized:
                    normalized.append(canonical)
            return normalized, skipped

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
            "router_suggested_tools": router_suggested,
        }
        with trace_node(
            "gather",
            inputs=node_inputs,
            metadata={"conversation_id": state.get("conversation_id")},
        ):
            router_canonical, router_skipped = _normalize_router_tools(router_suggested)
            for item in router_skipped:
                name = item["tool"]
                reason = f"{item['reason']} ({name})"
                tools_skipped.append(name)
                skip_reasons.append(reason)
                limitations.append(f"Suggested tool {name} is not available in the current registry.")
            for canonical in router_canonical:
                _append_unique(selected_before, canonical)

            # Existing deterministic intent-hint selection remains in place.
            if needs_portfolio:
                _append_unique(selected_before, "portfolio_analyzer")
            if needs_risk_check:
                _append_unique(selected_before, "risk_checker")
            if needs_market_data:
                _append_unique(selected_before, "market_data")
            if needs_macro_data:
                _append_unique(selected_before, "macro_data")
            if needs_sec_data:
                _append_unique(selected_before, "sec_filings")
            if needs_rag:
                _append_unique(selected_before, "rag_retriever")
            if needs_web:
                _append_unique(selected_before, "web_news")

            lowered = user_text.lower()
            intent = str(state.get("intent", ""))
            if (
                intent in {"portfolio_review", "portfolio_performance", "risk_check", "policy_breach_check", "scenario_simulation"}
                or any(k in lowered for k in ("portfolio", "risk", "policy", "scenario", "exposure"))
            ):
                _append_unique(selected_before, "portfolio_analyzer")
            if any(
                k in lowered
                for k in (
                    "internal policy",
                    "knowledge base",
                    "uploaded",
                    "committee notes",
                    "risk playbook",
                    "research notes",
                    "rag",
                )
            ):
                _append_unique(selected_before, "rag_retriever")
            if any(k in lowered for k in ("latest", "recent", "today", "moving", "news", "market event")):
                _append_unique(selected_before, "web_news")
            if any(k in lowered for k in ("price", "performance", "return", "p&l", "movement", "quote")):
                _append_unique(selected_before, "market_data")
            if any(k in lowered for k in ("rates", "fed", "inflation", "recession", "yields", "macro")):
                _append_unique(selected_before, "macro_data")
            if any(k in lowered for k in ("filings", "10-k", "10-q", "sec", "annual report", "risk factors")):
                _append_unique(selected_before, "sec_filings")
            scenario_requested = any(
                k in lowered for k in ("what-if", "what if", "shock", "drop", "rise", "downside", "upside", "stress", "scenario")
            ) or intent == "scenario_simulation"
            if scenario_requested:
                _append_unique(selected_before, "scenario_simulation")

            for canonical in selected_before:
                executable = _CANONICAL_TO_EXECUTABLE.get(canonical)
                if executable is None:
                    tools_skipped.append(canonical)
                    skip_reasons.append(f"No executable tool mapping for canonical tool '{canonical}'.")
                    limitations.append(f"Suggested tool {canonical} is not available in the current registry.")
                    continue
                if canonical == "scenario_simulation" and not registry.has(executable):
                    tools_skipped.append(canonical)
                    skip_reasons.append("Scenario tool unavailable; falling back to portfolio_analyzer deterministic estimate.")
                    limitations.append(
                        "Scenario estimate is first order and uses current portfolio exposure; full persisted scenario simulation is available on the Scenarios page."
                    )
                    if "portfolio_analyze" not in selected_after:
                        selected_after.append("portfolio_analyze")
                    continue
                if not registry.has(executable):
                    tools_skipped.append(canonical)
                    skip_reasons.append(f"Executable tool '{executable}' unavailable in registry.")
                    limitations.append(f"Suggested tool {canonical} is not available in the current registry.")
                    continue
                if executable not in selected_after:
                    selected_after.append(executable)

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
            for tool_name in selected_after:
                if tool_name == "market_quote":
                    _run("market_quote", tickers=tickers or _default_tickers())
                    continue
                if tool_name == "sec_filings":
                    for ticker in (tickers or _default_tickers()):
                        _run("sec_filings", ticker=ticker)
                    continue
                if tool_name == "rag_retrieve":
                    _run("rag_retrieve", query=user_text)
                    continue
                if tool_name == "web_search":
                    _run("web_search", query=user_text)
                    continue
                _run(tool_name)

        return {
            "evidence": evidence,
            "used_tools": used,
            "citations": citations,
            "tool_limitations": limitations,
            "graph_input_suggested_tools": router_suggested,
            "gather_selected_tools_before": selected_before,
            "gather_selected_tools_after": selected_after,
            "tools_executed": used,
            "tools_skipped": tools_skipped,
            "skip_reasons": skip_reasons,
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
        elif intent == "scenario_simulation":
            recommendation = "inform"
            risk_level = "medium"
            confidence = 0.72
            reasoning_extra.append(
                "Scenario shock question; first-order estimate from current weights (demo data)."
            )
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
        portfolio_impact_out: float | None = None
        if intent == "scenario_simulation":
            portfolio_impact_out = _scenario_portfolio_impact_fraction(state)

    out_state: AgentState = {
        "recommendation": recommendation,
        "requires_approval": requires_approval,
        "risk_level": risk_level,
        "confidence": confidence,
        "reasoning": [*state.get("reasoning", []), *reasoning_extra],
        "answer": answer,
        "evidence": _expand_rag_evidence_for_response(state),
    }
    if portfolio_impact_out is not None:
        out_state["portfolio_impact"] = portfolio_impact_out
    return out_state


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


def _display_source_title(source: str) -> str:
    """Human-readable document label for evidence rows (not for executive prose)."""

    name = (source or "").strip() or "Internal document"
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    if base.lower().endswith(".md"):
        base = base[:-3]
    cleaned = base.replace("_", " ").strip()
    return cleaned or "Internal document"


def _compact_snippet(text: str, max_len: int = 120) -> str:
    one_line = " ".join(str(text).split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1].rstrip() + "…"


def _expand_rag_evidence_for_response(state: AgentState) -> list[dict[str, Any]]:
    """Split RAG tool output into per-source evidence rows; keep full chunk data off summaries."""

    out: list[dict[str, Any]] = []
    for ev in state.get("evidence", []):
        if ev.get("tool") != "rag_retrieve":
            out.append(ev)
            continue
        data = ev.get("data")
        if not isinstance(data, dict):
            out.append(ev)
            continue
        chunks = data.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            out.append(ev)
            continue
        for c in chunks[:4]:
            if not isinstance(c, dict):
                continue
            src = str(c.get("source", "document"))
            title = _display_source_title(src)
            snippet = _compact_snippet(str(c.get("text", "")), 140)
            out.append(
                {
                    "tool": "rag_retrieve",
                    "summary": f"{title}: {snippet}",
                    "data": {
                        "chunk_id": c.get("chunk_id"),
                        "source": src,
                        "score": c.get("score"),
                        "text": c.get("text"),
                    },
                }
            )
    return out


def _parse_shock_percent(text: str) -> float | None:
    match = _SHOCK_PCT_RE.search(text)
    if not match:
        return None
    val = float(match.group("num"))
    if match.group("sign"):
        val = -val
    return val


def _scenario_portfolio_impact_fraction(state: AgentState) -> float | None:
    text = _last_user_message(state)
    shock = _parse_shock_percent(text)
    if shock is None:
        return None
    tickers = state.get("tickers") or []
    ticker = str(tickers[0]).upper() if tickers else None
    portfolio = _evidence_data(state, "portfolio_analyze") or {}
    positions = portfolio.get("positions") if isinstance(portfolio, dict) else []
    if not ticker or not isinstance(positions, list):
        return None
    for item in positions:
        if isinstance(item, dict) and str(item.get("symbol", "")).upper() == ticker:
            weight = item.get("weight")
            if isinstance(weight, (int, float)):
                return float(weight) * (shock / 100.0)
    return None


def _format_scenario_simulation_answer(state: AgentState, extras: list[str]) -> str:
    text = _last_user_message(state)
    shock = _parse_shock_percent(text)
    tickers = state.get("tickers") or []
    ticker = str(tickers[0]).upper() if tickers else None
    if not ticker:
        for match in _TICKER_RE_NODES.findall(text):
            if match in _KNOWN_TICKERS_NODES:
                ticker = match
                break
    portfolio = _evidence_data(state, "portfolio_analyze") or {}
    positions = portfolio.get("positions") if isinstance(portfolio, dict) else []
    weight: float | None = None
    if ticker and isinstance(positions, list):
        for item in positions:
            if isinstance(item, dict) and str(item.get("symbol", "")).upper() == ticker:
                w = item.get("weight")
                if isinstance(w, (int, float)):
                    weight = float(w)
                break

    lines = [
        "Executive answer:",
        "Scenario-style price shock (demo portfolio, first-order linear estimate).",
        "",
        "Estimated portfolio impact:",
    ]
    if shock is None:
        lines.append(
            "- Specify a percentage move (e.g. \"10%\" or \"10 percent\") to quantify the shock."
        )
    elif weight is not None:
        approx_pct = weight * shock
        lines.append(
            f"- If {ticker} moves about {shock:+.1f}% and other positions are unchanged, "
            f"portfolio return is roughly {approx_pct:+.2f}% from this name alone "
            f"(weight ≈ {weight * 100:.2f}% × {shock:+.1f}% move)."
        )
    else:
        lines.append(
            f"- First-order estimate: portfolio return contribution ≈ (current {ticker} weight) × ({shock:+.1f}% move). "
            "Holdings snapshot did not include this symbol’s weight; open Portfolio or Scenarios for a full run."
        )

    lines.extend(
        [
            "",
            "Affected holding:",
            f"- {ticker or 'Unknown (add a ticker such as NVDA)'}",
            "",
            "Risk level:",
            "- Medium — scenario math is simplified and ignores correlations, beta, and derivatives.",
            "",
            "Recommendation / next step:",
            "- Treat as indicative only; use the Scenarios page for a persisted simulation when available.",
            "",
            "Limitations:",
            "- Synthetic holdings; linear approximation; not investment advice.",
        ]
    )
    if extras:
        lines.append("")
        lines.append(f"Notes: {' '.join(extras)}")
    return "\n".join(lines).strip()


def _format_answer(
    intent: str,
    recommendation: str,
    extras: list[str],
    state: AgentState,
) -> str:
    if intent == "scenario_simulation":
        return _format_scenario_simulation_answer(state, extras)
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
    trim_pct = POLICY.single_name_trim_threshold * 100
    max_pct = POLICY.single_name_max_weight * 100
    has_chunks = isinstance(chunks, list) and bool(chunks)
    parts: list[str] = []
    if has_chunks:
        parts.append(
            "Based on the internal policy documents indexed in the knowledge base, concentration should be judged against "
            f"the single-name trim review level ({trim_pct:.0f}%) and the maximum position limit ({max_pct:.0f}%). "
            "Exposure above the trim threshold is a candidate for reduction pending portfolio context; exposure above the "
            "maximum typically requires escalation."
        )
        parts.append(
            "Internal policy evidence was retrieved from the knowledge base; document-level excerpts appear under Key evidence "
            "and RAG sources."
        )
        parts.append(
            "Any trim or trade decision should go through the human approval workflow before execution."
        )
    else:
        parts.append(
            "No policy passages were retrieved from the knowledge base for this question. "
            f"As a structured fallback, the single-name maximum is near {max_pct:.0f}% and the trim review threshold is near {trim_pct:.0f}%."
        )
        parts.append("Confirm retrieval or rephrase the query to target the relevant policy sections.")
    if extras:
        parts.append(" ".join(extras))
    return " ".join(parts).strip()


def _format_investment_recommendation_answer(
    state: AgentState,
    recommendation: str,
    extras: list[str],
) -> str:
    tickers = state.get("tickers", []) or _default_tickers()
    tickers_str = ", ".join(tickers[:5])
    portfolio = _evidence_data(state, "portfolio_analyze") or {}
    positions = portfolio.get("positions") if isinstance(portfolio, dict) else []
    rag_data = _evidence_data(state, "rag_retrieve") or {}
    chunks = rag_data.get("chunks") if isinstance(rag_data, dict) else []
    has_rag = isinstance(chunks, list) and bool(chunks)
    trim_pct = POLICY.single_name_trim_threshold * 100
    max_pct = POLICY.single_name_max_weight * 100

    if recommendation == "trim":
        lead = (
            "Based on the portfolio snapshot and IPS-style limits, the highlighted position(s) warrant a trim review: "
            f"exposure above the {trim_pct:.0f}% trim threshold should be reduced subject to committee approval, and the "
            f"{max_pct:.0f}% level is treated as a hard maximum requiring escalation if breached."
        )
    elif recommendation == "escalate":
        lead = (
            "Policy limits appear breached in the current snapshot; escalate for committee review before any trade action "
            f"and realign to the {max_pct:.0f}% single-name ceiling and {trim_pct:.0f}% trim review guidance."
        )
    else:
        lead = (
            f"This recommendation ({recommendation}) was evaluated for {tickers_str} against trim ({trim_pct:.0f}%) and "
            f"maximum ({max_pct:.0f}%) single-name guidance in the demo policy set."
        )

    weight_sentence = ""
    focus = str(tickers[0]).upper() if tickers else ""
    if focus and isinstance(positions, list):
        for item in positions:
            if isinstance(item, dict) and str(item.get("symbol", "")).upper() == focus:
                w = item.get("weight")
                if isinstance(w, (int, float)):
                    weight_sentence = (
                        f" In the synthetic snapshot, {focus} is about {float(w) * 100:.2f}% of the portfolio—compare that weight "
                        "to the trim and maximum thresholds when deciding next steps."
                    )
                break

    rag_sentence = (
        " Internal policy evidence was retrieved from the knowledge base; supporting excerpts are under Key evidence and RAG sources."
        if has_rag
        else " No knowledge-base passages were retrieved on this turn; lean on structured thresholds and portfolio analytics, or retry retrieval."
    )
    approval_sentence = " Any execution action requires human approval in the workflow."
    limit_sentence = (
        " Limitations: holdings and indexed documents are synthetic or demo unless production providers and corpora are configured."
    )
    body = "".join([lead, weight_sentence, rag_sentence, approval_sentence, limit_sentence])
    if extras:
        body = f"{body} {' '.join(extras)}"
    return body.strip()


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
