"""Pydantic v2 schemas for usage tracking.

Covers LLM token consumption, estimated cost, and tool invocations.
Designed to be persisted to Postgres later; uses an in-memory store for now.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EventType = Literal[
    "llm_call",
    "llm_fallback",
    "llm_error",
    "tool_call",
    "tool_error",
    "cache_hit",
    "feedback_submitted",
    "report_generated",
    "scenario_simulated",
    "speech_uploaded",
]


class UsageEvent(BaseModel):
    """A single usage event (LLM call or tool invocation)."""

    model_config = ConfigDict(frozen=True)

    usage_id: str
    created_at: datetime
    user_id: str | None = None
    conversation_id: str | None = None
    event_type: EventType
    provider: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    tool_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageSummary(BaseModel):
    """Aggregated usage across all recorded events."""

    model_config = ConfigDict(frozen=True)

    total_events: int
    total_tokens: int
    estimated_cost_usd: float
    tool_calls: int
    llm_calls: int
