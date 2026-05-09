"""Structured-output schemas used by the LLM integration layer.

These shape what we ask the LLM to emit and what we accept back. Keeping
them strict (Pydantic v2, ``extra="forbid"``) means malformed model output
is rejected at the boundary rather than poisoning agent state.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from alphalens.schemas.common import APIModel

RouteAnswerType = Literal["investment_decision", "app_help", "out_of_scope", "clarification"]
RouteLanguage = Literal["en", "de", "fr", "ar", "unknown"]


class RouteClassification(APIModel):
    """LLM-only structured router output (strict JSON via OpenAI parse)."""

    answer_type: RouteAnswerType
    intent: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "portfolio_performance | policy_check | rag_question | market_news | macro | "
            "sec_filings | reports | scenarios | approvals | app_capability | app_usage | "
            "unrelated | ambiguous"
        ),
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    language: RouteLanguage = "unknown"
    reason: str = Field(default="", max_length=600)
    suggested_tools: list[str] = Field(default_factory=list)


class IntentClassification(APIModel):
    """Result of mapping the user's last message to an agent intent.

    ``needs_*`` flags drive deterministic tool selection in the gather node;
    the LLM only suggests *which* tools are relevant, never executes them.
    """

    intent: str = Field(..., min_length=1, max_length=64)
    tickers: list[str] = Field(default_factory=list)
    needs_market_data: bool = False
    needs_rag: bool = False
    needs_portfolio: bool = False
    needs_risk_check: bool = False
    needs_web_search: bool = False


class DecisionSynthesis(APIModel):
    """LLM-augmented reasoning trace produced from gathered evidence."""

    reasoning: list[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=2000)
    confidence_adjustment: float | None = Field(
        default=None,
        ge=-0.3,
        le=0.3,
        description="Optional [-0.3, +0.3] delta applied to deterministic confidence.",
    )
