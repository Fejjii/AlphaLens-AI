"""Deterministic LLM stand-in used when no API key is available.

Reproduces the keyword-based interpretation that predated the LLM
integration so behaviour is identical in test and offline environments.
"""

from __future__ import annotations

import re

from alphalens.integrations.llm.base import LLMClient
from alphalens.schemas.llm import DecisionSynthesis, IntentClassification

_TICKER_RE = re.compile(r"\b[A-Z]{2,5}\b")

_KNOWN_TICKERS: frozenset[str] = frozenset(
    {
        "NVDA", "MSFT", "AAPL", "TSM", "AVGO", "GOOGL", "AMZN",
        "META", "ASML", "CRM", "XOM", "CVX", "NEE", "JPM", "BRKB",
        "AMD", "ARM", "PLTR", "SHOP", "NOW", "LIN", "COST", "SLB",
        "UNH", "NET",
    }
)

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "portfolio_review": ("portfolio", "holdings", "exposure", "weights", "nav"),
    "risk_check": ("risk", "concentration", "drawdown", "limit", "sector"),
    "trade_idea": ("buy", "sell", "trim", "add", "increase", "decrease", "trade"),
    "research": ("research", "thesis", "memo", "outlook", "policy"),
    "market_news": ("news", "headline", "headlines"),
    "portfolio_performance": (
        "performance",
        "return",
        "p&l",
        "pnl",
        "nav",
        "contributor",
        "laggard",
        "last 1 month",
        "last month",
        "month",
        "contributors",
        "laggards",
    ),
    "policy_breach_check": (
        "policy breach",
        "policy rule",
        "breach",
        "violat",
        "threshold",
        "compliance",
        "within limit",
    ),
    "risk_review": ("risk review", "risk", "concentration", "drawdown", "limit", "sector"),
    "rag_policy_question": (
        "internal policy",
        "knowledge base",
        "rag",
        "policy documents",
        "policy",
        "playbook",
        "committee notes",
        "summarize policy",
    ),
    "investment_recommendation": (
        "buy",
        "sell",
        "trim",
        "add",
        "increase",
        "decrease",
        "recommend",
        "should i",
        "rebalance",
    ),
    "market_news_question": ("news", "headline", "headlines", "latest market", "catalyst"),
    "sec_filings_question": ("sec", "10-k", "10k", "10-q", "10q", "filing", "edgar"),
    "macro_question": ("macro", "fed", "rates", "inflation", "cpi", "gdp", "unemployment"),
    "general_question": ("hello", "help", "what can you do"),
}
_INTENT_PRIORITY: tuple[str, ...] = (
    "policy_breach_check",
    "portfolio_performance",
    "rag_policy_question",
    "investment_recommendation",
    "market_news_question",
    "sec_filings_question",
    "macro_question",
    "risk_review",
    "portfolio_review",
    "risk_check",
    "trade_idea",
    "research",
    "market_news",
    "general_question",
)

# Keywords that signal the user wants fresh external context, regardless
# of intent. Mirrored in the agent gather node as a defensive backup so
# behaviour is identical with or without an LLM-backed primary.
_WEB_SEARCH_KEYWORDS: tuple[str, ...] = (
    "news", "market", "latest", "recent", "today", "macro",
    "earnings", "catalyst", "risk", "opportunity", "headline", "headlines",
)

_EXPLICIT_RAG_TERMS: tuple[str, ...] = (
    "rag",
    "knowledge base",
    "internal policy",
    "policy document",
    "policy documents",
    "investment policy",
    "risk playbook",
    "committee notes",
    "research notes",
    "internal documents",
    "uploaded document",
    "summarize policy",
    "source from kb",
)


def needs_web_search(text: str, intent: str) -> bool:
    """Heuristic: does the message warrant a public web/news lookup?"""

    lowered = text.lower()
    if any(term in lowered for term in _WEB_SEARCH_KEYWORDS):
        return True
    return intent in {"investment_recommendation", "market_news_question", "macro_question", "sec_filings_question"}


def needs_rag_explicitly(text: str, intent: str) -> bool:
    """Return True when user asks for KB/policy-grounded evidence."""

    lowered = text.lower()
    if any(term in lowered for term in _EXPLICIT_RAG_TERMS):
        return True
    return intent in {"rag_policy_question", "policy_breach_check", "investment_recommendation"}


def _classify_intent(text: str) -> str:
    lowered = text.lower()
    for intent in _INTENT_PRIORITY:
        terms = _INTENT_KEYWORDS.get(intent, ())
        if any(term in lowered for term in terms):
            return intent
    return "general_question"


def _extract_tickers(text: str) -> list[str]:
    return sorted({m for m in _TICKER_RE.findall(text) if m in _KNOWN_TICKERS})


class DeterministicFallbackLLMClient(LLMClient):
    """Keyword-based intent classifier and pass-through synthesizer."""

    def classify_intent(self, *, message: str) -> IntentClassification:
        intent = _classify_intent(message)
        tickers = _extract_tickers(message)
        rag_requested = needs_rag_explicitly(message, intent)
        recommendation_context = (
            bool(tickers)
            and any(term in message.lower() for term in ("trim", "should", "recommend", "rebalance"))
        )
        needs_portfolio = intent in {
            "portfolio_performance",
            "policy_breach_check",
            "risk_review",
            "investment_recommendation",
            "portfolio_review",
            "risk_check",
            "trade_idea",
        } or recommendation_context
        needs_risk_check = intent in {
            "policy_breach_check",
            "risk_review",
            "investment_recommendation",
            "portfolio_review",
            "risk_check",
            "trade_idea",
        } or recommendation_context
        needs_market_data = intent in {
            "portfolio_performance",
            "investment_recommendation",
            "market_news_question",
            "trade_idea",
            "market_news",
        } or bool(tickers)
        needs_rag = rag_requested or intent in {
            "research",
            "trade_idea",
            "risk_check",
        }
        return IntentClassification(
            intent=intent,
            tickers=tickers,
            needs_market_data=needs_market_data,
            needs_rag=needs_rag,
            needs_portfolio=needs_portfolio,
            needs_risk_check=needs_risk_check,
            needs_web_search=needs_web_search(message, intent),
        )

    def synthesize_decision(
        self,
        *,
        intent: str,
        recommendation: str,
        evidence: list[dict],
        deterministic_reasoning: list[str],
    ) -> DecisionSynthesis:
        # Deterministic mode: hand back the existing reasoning trace unchanged
        # and don't second-guess the rule-based confidence.
        summary = (
            f"Intent {intent}; recommendation {recommendation} based on "
            f"{len(evidence)} piece(s) of evidence."
        )
        return DecisionSynthesis(
            reasoning=list(deterministic_reasoning),
            summary=summary,
            confidence_adjustment=None,
        )
