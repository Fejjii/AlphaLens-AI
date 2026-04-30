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
}

# Keywords that signal the user wants fresh external context, regardless
# of intent. Mirrored in the agent gather node as a defensive backup so
# behaviour is identical with or without an LLM-backed primary.
_WEB_SEARCH_KEYWORDS: tuple[str, ...] = (
    "news", "market", "latest", "recent", "today", "macro",
    "earnings", "catalyst", "risk", "opportunity", "headline", "headlines",
)


def needs_web_search(text: str, intent: str) -> bool:
    """Heuristic: does the message warrant a public web/news lookup?"""

    lowered = text.lower()
    if any(term in lowered for term in _WEB_SEARCH_KEYWORDS):
        return True
    return intent in {"trade_idea", "research", "risk_check", "market_news"}


def _classify_intent(text: str) -> str:
    lowered = text.lower()
    for intent, terms in _INTENT_KEYWORDS.items():
        if any(term in lowered for term in terms):
            return intent
    return "general"


def _extract_tickers(text: str) -> list[str]:
    return sorted({m for m in _TICKER_RE.findall(text) if m in _KNOWN_TICKERS})


class DeterministicFallbackLLMClient(LLMClient):
    """Keyword-based intent classifier and pass-through synthesizer."""

    def classify_intent(self, *, message: str) -> IntentClassification:
        intent = _classify_intent(message)
        tickers = _extract_tickers(message)
        needs_portfolio = intent in {"portfolio_review", "risk_check", "trade_idea"}
        needs_risk_check = intent in {"portfolio_review", "risk_check", "trade_idea"}
        needs_market_data = intent == "trade_idea" or bool(tickers)
        needs_rag = intent in {"research", "trade_idea", "risk_check"}
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
