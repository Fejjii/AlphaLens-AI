"""Layered chat domain router: guardrails, optional LLM JSON classify, deterministic fallback."""

from __future__ import annotations

import re
from typing import Any, Callable

from alphalens.schemas.agent import ChatAnswerType, ChatRouting
from alphalens.schemas.llm import RouteClassification

# --- Tool ids aligned with registered LangGraph tools ---
_CANONICAL_TOOLS: dict[str, str] = {
    "rag_retriever": "rag_retrieve",
    "rag_retrieve": "rag_retrieve",
    "web_news": "web_search",
    "web_search": "web_search",
    "market_data": "market_quote",
    "market_quote": "market_quote",
    "macro": "macro_snapshot",
    "macro_snapshot": "macro_snapshot",
    "sec": "sec_filings",
    "sec_filings": "sec_filings",
    "portfolio_analyzer": "portfolio_analyze",
    "portfolio_analyze": "portfolio_analyze",
    "policy_rules": "risk_check",
    "policy_risk": "risk_check",
    "risk_check": "risk_check",
}

_ALLOWED_TOOL_IDS = frozenset(_CANONICAL_TOOLS.values())


def normalize_suggested_tools(raw: list[str] | None) -> list[str]:
    out: list[str] = []
    if not raw:
        return out
    for item in raw:
        key = (item or "").strip().lower().replace(" ", "_")
        mapped = _CANONICAL_TOOLS.get(key, key)
        if mapped in _ALLOWED_TOOL_IDS and mapped not in out:
            out.append(mapped)
    return out


_INVESTMENT_CONTENT_RE = re.compile(
    r"\b("
    r"portfolio|holding|holdings|nav|allocation|rebalanc|exposure|diversif|"
    r"risk\s*review|risk\s+check|\brisk\b|breach|mandate|compliance|concentrat|"
    r"weight(s)?|position(s)?|performance|return(s)?|pnl|p&l|drawdown|volatility|var\b|"
    r"trim|rebalance|\bbuy\b|\bsell\b|escalate|"
    r"rag\b|retriev|knowledge\s*base|\bkb\b|internal\s+document|investment\s+policy|"
    r"risk\s+playbook|committee|research\s+note|qdrant|vector|chunk|"
    r"macro|fred\b|fed\b|cpi\b|pce\b|inflation|interest\s+rate|yield\s+curve|recession|"
    r"\bsec\b|edgar|filing|filings|10-?\s*k\b|10-?\s*q\b|annual\s+report|"
    r"market\s*(data|quote|price)|stock\s*price|\bticker\b|equity|etf|bond|yield|"
    r"nvda|aapl|msft|googl|amzn|tsla|meta\b|microsoft|apple|google|amazon|tesla|"
    r"sp500|s&p|"
    r"investment|investable|asset\s*class|benchmark"
    r")\b",
    re.IGNORECASE,
)

# Investment-oriented "approval" (not "how do approvals work in the app").
_INVESTMENT_APPROVAL_RE = re.compile(
    r"\b("
    r"requires?\s+approval|approval\s+required|trade\s+approval|pending\s+approval|"
    r"approval\s+queue|approval\s+gate|escalat(e|ion)"
    r")\b",
    re.IGNORECASE,
)

_SCENARIO_INVESTMENT_RE = re.compile(
    r"\b("
    r"stress\s+scenario|scenario\s+analysis|base\s+case|what\s+if|what\s+happens\s+if|"
    r"monte\s+carlo|price\s+shock|\bshock\b"
    r")\b",
    re.IGNORECASE,
)

_SCENARIO_SHOCK_CUES_RE = re.compile(
    r"(what\s+if|what\s+happens\s+if|drops?\b|dropped\b|falls?\b|fell\b|declin(e|es|ed|ing)\b|"
    r"down\s+\d|\-\s*\d+\s*(?:%|percent)|\d+\s*(?:%|percent))",
    re.IGNORECASE,
)

_REPORT_INVESTMENT_RE = re.compile(
    r"\b(investment\s+report|portfolio\s+report|committee\s+report|memo\s+for\s+committee)\b",
    re.IGNORECASE,
)

_APP_HELP_STRONG_RE = re.compile(
    r"\b("
    r"what\s+can\s+you\s+do|what\s+are\s+you|who\s+are\s+you|"
    r"how\s+does\s+alphalens|how\s+alphalens|what\s+is\s+alphalens|"
    r"capabilities|limitations|your\s+limitations|"
    r"what\s+tools|which\s+tools|tools\s+(do\s+you\s+have|are\s+available)|"
    r"how\s+many\s+languages|languages?\s+do\s+you\s+support|supported\s+languages|"
    r"multilingual|speech\s+work|voice\s+work|"
    r"understand\s+(french|german|arabic|english|spanish|deutsch|français|francais)|"
    r"speak\s+(french|german|arabic|english)|"
    r"answer\s+in\s+(french|german|arabic)|"
    r"do\s+you\s+(speak|understand|support)|can\s+i\s+talk\s+to\s+you\s+in|"
    r"can\s+you\s+(speak|understand|answer)|"
    r"handle\s+german|handle\s+french|"
    r"how\s+do\s+i\s+upload|how\s+to\s+upload|upload\s+documents?|"
    r"how\s+do\s+reports\s+work|how\s+reports\s+work|"
    r"how\s+do\s+scenarios\s+work|"
    r"how\s+does\s+rag\s+work(\s+here)?|explain\s+rag|"
    r"what\s+data\s+do\s+you\s+use"
    r")\b",
    re.IGNORECASE,
)

# Meta questions about product workflows (not data pulls).
_APP_META_HOW_RE = re.compile(
    r"(?i)^\s*(how|what|where|when|why|which)\s+.+\b("
    r"work|working|upload|export|configure|settings|limitations|capabilities|"
    r"approval\s+flow|approvals\s+work|reports\s+work|scenarios\s+work|"
    r"this\s+app|the\s+app|alphalens"
    r")\b",
)

_OUT_OF_SCOPE_RE = re.compile(
    r"\b("
    r"weather|forecast|météo|wetter|recipe|cook(ing)?|pasta|"
    r"kitchen|restaurant recommendation|movie recommendation|"
    r"sports\s*score|football|nba\b|nfl\b|world\s+cup|"
    r"medicine|doctor|diagnosis|legal\s+advice|lawyer|attorney|"
    r"trivia|celebrity\s+gossip"
    r")\b",
    re.IGNORECASE,
)

_AMBIGUOUS_RE = re.compile(
    r"(?i)^\s*("
    r"should\s+i\s+do\s+it|what\s+about\s+(this|that|it)\??|"
    r"^analyze\s+(this|that|it)\.?\s*$|"
    r"is\s+this\s+okay\??|tell\s+me\s+more\.?\s*$|"
    r"^what\s+about\s+tomorrow\??\s*$"
    r")",
)

_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")

_KNOWN_TICKERS: frozenset[str] = frozenset(
    {
        "NVDA", "MSFT", "AAPL", "TSM", "AVGO", "GOOGL", "AMZN",
        "META", "ASML", "CRM", "XOM", "CVX", "NEE", "JPM", "BRKB",
        "AMD", "ARM", "PLTR", "SHOP", "NOW", "LIN", "COST", "SLB",
        "UNH", "NET", "SPY", "QQQ",
    }
)


_APP_HELP_FRAGMENTS = (
    "français",
    "francais",
    "comprends",
    "comprenez",
    "est-ce que",
    "est ce que",
    "peux-tu",
    "pouvez-vous",
    "verstehst du",
    "verstehen sie",
    "welche sprachen",
    "unterstützt du",
    "unterstutzt du",
    "deutsch",
    "auf deutsch",
    "هل تفهم",
    "العربية",
    "تتحدث",
    "كم لغة",
)

_APP_HELP_KEYWORD_HITS: tuple[tuple[str, ...], ...] = (
    ("language", "languages", "speak", "understand", "multilingual", "speech", "voice"),
    ("french", "german", "arabic", "english", "français", "francais", "deutsch", "anglais", "arabe"),
    ("what can you do", "capabilities", "limitations", "alphalens"),
    ("how does this app", "how do you work", "how does alphalens"),
    ("upload", "documents", "knowledge base upload"),
)

_INVESTMENT_KEYWORD_HITS: tuple[tuple[str, ...], ...] = (
    ("portfolio", "holding", "position", "exposure", "weight", "nav", "pnl", "p&l", "performance", "return"),
    ("risk", "policy", "mandate", "breach", "limit", "concentration", "concentrated"),
    ("trim", "rebalance", "buy", "sell", "hold", "escalate"),
    ("market", "news", "macro", "inflation", "rates", "fed", "sec", "filing", "10-k", "10-q"),
    ("rag", "knowledge base", "internal document", "investment policy", "risk playbook", "committee", "research note"),
)

_OUT_OF_SCOPE_KEYWORD_HITS: tuple[tuple[str, ...], ...] = (
    ("weather", "forecast", "recipe", "cooking", "travel", "trip", "flight"),
    ("football", "sports score", "nba", "nfl"),
    ("medicine", "doctor", "legal advice", "lawyer"),
    ("homework", "essay", "trivia"),
)


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _score_keyword_families(lowered: str, families: tuple[tuple[str, ...], ...]) -> int:
    score = 0
    for group in families:
        if any(term in lowered for term in group):
            score += 1
    return score


def thread_has_investment_context(prior_messages: list[dict[str, Any]]) -> bool:
    """True when the thread is genuinely about an investment workflow.

    Assistant turns with answer_type app_help / out_of_scope / clarification are **ignored**
    for keyword scans: their boilerplate mentions portfolio/RAG/market and would otherwise
    poison follow-ups like \"Should I do it?\".
    """
    window = prior_messages[-8:] if prior_messages else []
    for msg in window:
        role = msg.get("role")
        if role not in {"user", "assistant"}:
            continue
        meta = msg.get("metadata") or {}
        at = meta.get("answer_type")

        if role == "assistant":
            if at in {
                ChatAnswerType.APP_HELP.value,
                ChatAnswerType.OUT_OF_SCOPE.value,
                ChatAnswerType.CLARIFICATION.value,
            }:
                continue
            if at == ChatAnswerType.INVESTMENT_DECISION.value or meta.get("decision"):
                return True
            # Legacy rows without answer_type: do not scan assistant body text (often generic).
            if at is None and not meta.get("decision"):
                continue
            content = str(msg.get("content", ""))
            if _INVESTMENT_APPROVAL_RE.search(content):
                return True
            if _TICKER_RE.search(content):
                for m in _TICKER_RE.findall(content):
                    if m in _KNOWN_TICKERS:
                        return True
            continue

        content = str(msg.get("content", ""))
        if _INVESTMENT_CONTENT_RE.search(content):
            return True
        if _INVESTMENT_APPROVAL_RE.search(content):
            return True
        if _TICKER_RE.search(content):
            for m in _TICKER_RE.findall(content):
                if m in _KNOWN_TICKERS:
                    return True
    return False


def _infer_suggested_tools(lowered: str) -> list[str]:
    tools: list[str] = []
    if any(
        t in lowered
        for t in (
            "internal policy",
            "knowledge base",
            "rag",
            "uploaded",
            "committee notes",
            "risk playbook",
            "investment policy",
            "internal document",
        )
    ):
        tools.append("rag_retrieve")
    if any(
        t in lowered
        for t in (
            "news",
            "headline",
            "today",
            "moving",
            "moved",
            "catalyst",
            "earnings",
            "why is",
            "what happened",
        )
    ):
        tools.append("web_search")
    if any(t in lowered for t in ("price", "quote", "return", "performance", "valuation", "pe ratio", "market cap")):
        tools.append("market_quote")
    if any(t in lowered for t in ("fed", "rates", "inflation", "macro", "yield", "recession", "cpi")):
        tools.append("macro_snapshot")
    if any(t in lowered for t in ("10-k", "10k", "10-q", "10q", "sec", "filing", "edgar", "annual report")):
        tools.append("sec_filings")
    if any(t in lowered for t in ("portfolio", "holding", "weight", "nav", "pnl", "exposure", "concentration")):
        tools.append("portfolio_analyze")
    if any(t in lowered for t in ("mandate", "breach", "policy", "limit", "compliance", "rule")):
        tools.append("risk_check")
    return normalize_suggested_tools(tools)


def _is_scenario_shock_prompt(lowered: str) -> bool:
    if _SCENARIO_INVESTMENT_RE.search(lowered):
        return True
    if _SCENARIO_SHOCK_CUES_RE.search(lowered) and (
        _TICKER_RE.search(lowered) or "portfolio" in lowered
    ):
        return True
    return False


def _matches_investment(lowered: str) -> bool:
    if _INVESTMENT_CONTENT_RE.search(lowered):
        return True
    if _INVESTMENT_APPROVAL_RE.search(lowered):
        return True
    if _SCENARIO_INVESTMENT_RE.search(lowered):
        return True
    if _is_scenario_shock_prompt(lowered):
        return True
    if _REPORT_INVESTMENT_RE.search(lowered):
        return True
    for m in _TICKER_RE.findall(lowered):
        if m in _KNOWN_TICKERS:
            return True
    if _score_keyword_families(lowered, _INVESTMENT_KEYWORD_HITS) >= 2:
        return True
    if _score_keyword_families(lowered, _INVESTMENT_KEYWORD_HITS) == 1 and (
        "?" in lowered or "how" in lowered or "what" in lowered or "why" in lowered
    ):
        return True
    return False


def _matches_app_help(lowered: str) -> bool:
    if _APP_HELP_STRONG_RE.search(lowered):
        return True
    if _APP_META_HOW_RE.search(lowered):
        return True
    for frag in _APP_HELP_FRAGMENTS:
        if frag in lowered:
            return True
    if _score_keyword_families(lowered, _APP_HELP_KEYWORD_HITS) >= 2:
        return True
    return False


def _matches_out_of_scope(lowered: str) -> bool:
    if _OUT_OF_SCOPE_RE.search(lowered):
        return True
    if _score_keyword_families(lowered, _OUT_OF_SCOPE_KEYWORD_HITS) >= 2:
        return True
    return False


def _layer_a_deterministic(
    text: str,
    lowered: str,
    *,
    prior_messages: list[dict[str, Any]],
    detected_language: str,
) -> ChatRouting | None:
    if not text:
        return ChatRouting(
            answer_type=ChatAnswerType.APP_HELP.value,
            intent="app_capability",
            confidence=1.0,
            language=detected_language,
            reason="empty_prompt",
            suggested_tools=[],
            router_source="deterministic_guard",
        )

    inv_ctx = thread_has_investment_context(prior_messages)

    if len(text) <= 72 and re.match(
        r"^(hi|hello|hey|good\s+(morning|afternoon|evening)|thanks|thank\s+you|ok|okay|great)\b",
        lowered,
    ):
        return ChatRouting(
            answer_type=ChatAnswerType.APP_HELP.value,
            intent="app_usage",
            confidence=0.9,
            language=detected_language,
            reason="short_greeting_or_acknowledgement",
            suggested_tools=[],
            router_source="deterministic_guard",
        )

    if _matches_app_help(lowered):
        inv_hit = _matches_investment(lowered)
        if not inv_hit:
            return ChatRouting(
                answer_type=ChatAnswerType.APP_HELP.value,
                intent="app_capability",
                confidence=0.97,
                language=detected_language,
                reason="deterministic_app_help_cues",
                suggested_tools=[],
                router_source="deterministic_guard",
            )
        anchored = bool(_TICKER_RE.search(lowered) or re.search(r"\b(my|our)\s+portfolio\b", lowered))
        if anchored:
            pass  # fall through to investment
        elif _APP_META_HOW_RE.search(lowered):
            return ChatRouting(
                answer_type=ChatAnswerType.APP_HELP.value,
                intent="app_capability",
                confidence=0.94,
                language=detected_language,
                reason="meta_product_question_overlaps_finance_terms",
                suggested_tools=[],
                router_source="deterministic_guard",
            )
        # else: mixed cues, continue to investment rules below

    if _matches_out_of_scope(lowered) and not _matches_investment(lowered):
        return ChatRouting(
            answer_type=ChatAnswerType.OUT_OF_SCOPE.value,
            intent="unrelated",
            confidence=0.95,
            language=detected_language,
            reason="deterministic_off_topic_cues",
            suggested_tools=[],
            router_source="deterministic_guard",
        )

    if _AMBIGUOUS_RE.search(lowered) and not inv_ctx:
        return ChatRouting(
            answer_type=ChatAnswerType.CLARIFICATION.value,
            intent="ambiguous",
            confidence=0.9,
            language=detected_language,
            reason="ambiguous_without_investment_context",
            suggested_tools=[],
            router_source="deterministic_guard",
        )

    if _matches_investment(lowered):
        tools = _infer_suggested_tools(lowered)
        intent_guess = "portfolio_performance"
        if _is_scenario_shock_prompt(lowered):
            intent_guess = "scenario_simulation"
            tools = normalize_suggested_tools(["portfolio_analyze"])
        elif "rag" in lowered or "knowledge base" in lowered or "internal document" in lowered:
            intent_guess = "rag_question"
        elif "policy" in lowered or "mandate" in lowered or "breach" in lowered:
            intent_guess = "policy_check"
        elif "news" in lowered or "today" in lowered or "moving" in lowered or "happened" in lowered:
            intent_guess = "market_news"
        elif "10-k" in lowered or "10-q" in lowered or "sec" in lowered or "filing" in lowered:
            intent_guess = "sec_filings"
        elif "fed" in lowered or "inflation" in lowered or "rates" in lowered or "macro" in lowered:
            intent_guess = "macro"
        return ChatRouting(
            answer_type=ChatAnswerType.INVESTMENT_DECISION.value,
            intent=intent_guess,
            confidence=0.93,
            language=detected_language,
            reason="deterministic_investment_cues",
            suggested_tools=tools,
            router_source="deterministic_guard",
        )

    if (
        inv_ctx
        and len(text) <= 160
        and not _matches_app_help(lowered)
        and not (_matches_out_of_scope(lowered) and not _matches_investment(lowered))
    ):
        tools = _infer_suggested_tools(lowered)
        return ChatRouting(
            answer_type=ChatAnswerType.INVESTMENT_DECISION.value,
            intent="portfolio_performance",
            confidence=0.78,
            language=detected_language,
            reason="investment_thread_short_follow_up",
            suggested_tools=tools,
            router_source="deterministic_guard",
        )

    return None


def _layer_c_fallback(
    text: str,
    lowered: str,
    *,
    prior_messages: list[dict[str, Any]],
    detected_language: str,
) -> ChatRouting:
    inv_ctx = thread_has_investment_context(prior_messages)
    app_s = _score_keyword_families(lowered, _APP_HELP_KEYWORD_HITS)
    inv_s = _score_keyword_families(lowered, _INVESTMENT_KEYWORD_HITS)
    oos_s = _score_keyword_families(lowered, _OUT_OF_SCOPE_KEYWORD_HITS)

    ambiguous_only = bool(_AMBIGUOUS_RE.search(lowered)) or (
        len(text.split()) <= 4 and bool(re.search(r"\b(it|this|that)\b", lowered))
    )

    if ambiguous_only and not inv_ctx:
        return ChatRouting(
            answer_type=ChatAnswerType.CLARIFICATION.value,
            intent="ambiguous",
            confidence=0.72,
            language=detected_language,
            reason="fallback_ambiguous",
            suggested_tools=[],
            router_source="deterministic_fallback",
        )

    if app_s >= 2 and inv_s == 0:
        return ChatRouting(
            answer_type=ChatAnswerType.APP_HELP.value,
            intent="app_usage",
            confidence=min(0.55 + 0.1 * app_s, 0.88),
            language=detected_language,
            reason="fallback_app_help_keyword_families",
            suggested_tools=[],
            router_source="deterministic_fallback",
        )

    if oos_s >= 2 and inv_s == 0:
        return ChatRouting(
            answer_type=ChatAnswerType.OUT_OF_SCOPE.value,
            intent="unrelated",
            confidence=min(0.55 + 0.12 * oos_s, 0.9),
            language=detected_language,
            reason="fallback_off_topic_keyword_families",
            suggested_tools=[],
            router_source="deterministic_fallback",
        )

    if inv_s >= 1 or _matches_investment(lowered):
        tools = _infer_suggested_tools(lowered)
        return ChatRouting(
            answer_type=ChatAnswerType.INVESTMENT_DECISION.value,
            intent="portfolio_performance",
            confidence=min(0.5 + 0.15 * inv_s, 0.85),
            language=detected_language,
            reason="fallback_investment_keyword_families",
            suggested_tools=tools,
            router_source="deterministic_fallback",
        )

    if oos_s >= 1 and app_s == 0:
        return ChatRouting(
            answer_type=ChatAnswerType.OUT_OF_SCOPE.value,
            intent="unrelated",
            confidence=0.55,
            language=detected_language,
            reason="fallback_weak_off_topic",
            suggested_tools=[],
            router_source="deterministic_fallback",
        )

    return ChatRouting(
        answer_type=ChatAnswerType.CLARIFICATION.value,
        intent="ambiguous",
        confidence=0.6,
        language=detected_language,
        reason="fallback_unclear_default_clarification",
        suggested_tools=[],
        router_source="deterministic_fallback",
    )


def _coerce_route_classification(rc: RouteClassification) -> ChatRouting:
    at_raw = (rc.answer_type or "").strip().lower()
    try:
        at = ChatAnswerType(at_raw)
        answer_type_str = at.value
    except ValueError:
        answer_type_str = ChatAnswerType.CLARIFICATION.value

    lang = (rc.language or "unknown").lower().split("-", 1)[0]
    if lang not in {"en", "de", "fr", "ar"}:
        lang = "unknown"

    tools = normalize_suggested_tools(list(rc.suggested_tools or []))
    if answer_type_str != ChatAnswerType.INVESTMENT_DECISION.value:
        tools = []

    return ChatRouting(
        answer_type=answer_type_str,
        intent=(rc.intent or "ambiguous").strip()[:64] or "ambiguous",
        confidence=float(rc.confidence),
        language=lang,
        reason=(rc.reason or "llm_router").strip()[:600],
        suggested_tools=tools,
        router_source="llm",
    )


def resolve_chat_route(
    user_text: str,
    *,
    prior_messages: list[dict[str, Any]] | None,
    detected_language: str,
    confidence_threshold: float,
    llm_classify: Callable[[str], RouteClassification] | None = None,
) -> ChatRouting:
    """Layer A → optional LLM (B) → layer C. Applies confidence guard after LLM."""
    prior = list(prior_messages or [])
    text = (user_text or "").strip()
    lowered = _normalize(text)
    lang = (detected_language or "en").lower().split("-", 1)[0]
    if lang not in {"en", "de", "fr", "ar"}:
        lang = "unknown"

    hit = _layer_a_deterministic(text, lowered, prior_messages=prior, detected_language=lang)
    if hit is not None:
        return hit

    if llm_classify is not None and text:
        try:
            raw = llm_classify(text)
            routed = _coerce_route_classification(raw)
            if routed.confidence < confidence_threshold:
                return ChatRouting(
                    answer_type=ChatAnswerType.CLARIFICATION.value,
                    intent="ambiguous",
                    confidence=routed.confidence,
                    language=lang,
                    reason=f"below_threshold_llm:{routed.reason[:200]}",
                    suggested_tools=[],
                    router_source="llm_low_confidence",
                )
            if routed.answer_type == ChatAnswerType.INVESTMENT_DECISION.value and routed.confidence < max(
                confidence_threshold, 0.68
            ):
                return ChatRouting(
                    answer_type=ChatAnswerType.CLARIFICATION.value,
                    intent="ambiguous",
                    confidence=routed.confidence,
                    language=lang,
                    reason="investment_route_requires_higher_confidence",
                    suggested_tools=[],
                    router_source="llm_low_confidence",
                )
            return routed
        except Exception:
            pass

    return _layer_c_fallback(text, lowered, prior_messages=prior, detected_language=lang)


def clarification_reply(response_language: str) -> str:
    lang = (response_language or "en").lower().split("-", 1)[0]
    if lang == "fr":
        return (
            "Que souhaitez-vous que j’évalue : une action de portefeuille, un écart de politique, "
            "un événement de marché, ou une question basée sur des documents ?"
        )
    if lang == "de":
        return (
            "Was soll ich bewerten: eine Portfolio-Maßnahme, einen Policy-Verstoß, "
            "ein Marktereignis oder eine dokumentenbasierte Frage?"
        )
    if lang == "ar":
        return (
            "ماذا تريد أن أقيّم: إجراءً متعلقًا بالمحفظة، أم خرق سياسة، أم حدثًا سوقيًا، أم سؤالًا يعتمد على المستندات؟"
        )
    return (
        "What would you like me to evaluate: a portfolio action, a policy breach, "
        "a market event, or a document-based question?"
    )
