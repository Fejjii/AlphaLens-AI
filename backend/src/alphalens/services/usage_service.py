"""Usage tracking service.

Records LLM calls (token counts, estimated cost) and tool invocations into
an in-memory store.  The interface is designed so the backing store can be
swapped to Postgres later with no changes at call sites.

Cost constants are approximate list prices as of early 2026 and are only
used for transparency estimates — not billing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from alphalens.repositories.usage import InMemoryUsageRepository, UsageRepository
from alphalens.schemas.usage import EventType, UsageEvent, UsageSummary

# ---------------------------------------------------------------------------
# Approximate pricing constants (USD per 1 000 tokens, input / output)
# Source: OpenAI pricing page, approximate list prices.
# ---------------------------------------------------------------------------
_COST_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.010, 0.030),
    "gpt-4": (0.030, 0.060),
    "gpt-3.5-turbo": (0.0005, 0.0015),
}
_DEFAULT_COST_PER_1K: tuple[float, float] = (0.001, 0.002)


def _estimate_cost(model: str | None, input_tokens: int, output_tokens: int) -> float:
    if model is None:
        return 0.0
    # Normalize: strip version suffixes like "-0125" for lookup.
    base = model.lower().split("-202")[0]
    rates = _COST_PER_1K.get(base, _DEFAULT_COST_PER_1K)
    return (input_tokens * rates[0] + output_tokens * rates[1]) / 1000.0


class UsageService:
    """In-memory usage event store.

    Thread-safety: the GIL protects list.append() in CPython; this is
    sufficient for the current single-process deployment.
    """

    def __init__(self, repository: UsageRepository | None = None) -> None:
        self._repository = repository or InMemoryUsageRepository()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_llm_usage(
        self,
        *,
        event_type: EventType = "llm_call",
        provider: str,
        user_id: str | None = None,
        model: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEvent:
        total = input_tokens + output_tokens
        cost = _estimate_cost(model, input_tokens, output_tokens)
        event = UsageEvent(
            usage_id=f"use_{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(tz=UTC),
            user_id=user_id,
            conversation_id=conversation_id,
            event_type=event_type,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost_usd=cost,
            metadata=metadata or {},
        )
        return self._repository.create(event)

    def record_tool_usage(
        self,
        *,
        tool_name: str,
        success: bool,
        provider: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEvent:
        event = UsageEvent(
            usage_id=f"use_{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(tz=UTC),
            user_id=user_id,
            conversation_id=conversation_id,
            event_type="tool_call" if success else "tool_error",
            provider=provider or "unknown",
            tool_name=tool_name,
            metadata=metadata or {},
        )
        return self._repository.create(event)

    def record_event(
        self,
        *,
        event_type: EventType,
        provider: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEvent:
        event = UsageEvent(
            usage_id=f"use_{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(tz=UTC),
            user_id=user_id,
            conversation_id=conversation_id,
            event_type=event_type,
            provider=provider,
            metadata=metadata or {},
        )
        return self._repository.create(event)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def list_usage_events(self, *, user_id: str | None = None) -> list[UsageEvent]:
        return self._repository.list(user_id=user_id)

    def get_usage_summary(self, *, user_id: str | None = None) -> UsageSummary:
        total_tokens = 0
        total_cost = 0.0
        tool_calls = 0
        llm_calls = 0
        events = self.list_usage_events(user_id=user_id)

        for ev in events:
            total_tokens += ev.total_tokens or 0
            total_cost += ev.estimated_cost_usd or 0.0
            if ev.event_type in {"llm_call", "llm_fallback", "llm_error"}:
                llm_calls += 1
            elif ev.event_type in {"tool_call", "tool_error"}:
                tool_calls += 1

        return UsageSummary(
            total_events=len(events),
            total_tokens=total_tokens,
            estimated_cost_usd=round(total_cost, 8),
            tool_calls=tool_calls,
            llm_calls=llm_calls,
        )

    def reset(self) -> None:
        """Clear all events. Useful for test isolation."""
        clear = getattr(self._repository, "clear", None)
        if callable(clear):
            clear()
