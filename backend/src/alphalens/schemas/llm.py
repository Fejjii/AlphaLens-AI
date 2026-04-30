"""Structured-output schemas used by the LLM integration layer.

These shape what we ask the LLM to emit and what we accept back. Keeping
them strict (Pydantic v2, ``extra="forbid"``) means malformed model output
is rejected at the boundary rather than poisoning agent state.
"""

from __future__ import annotations

from pydantic import Field

from alphalens.schemas.common import APIModel


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
