"""Protocol for LLM clients used by the AlphaLens agent."""

from __future__ import annotations

from typing import Protocol

from alphalens.schemas.llm import DecisionSynthesis, IntentClassification


class LLMError(Exception):
    """Raised by an `LLMClient` when an upstream call fails for any reason.

    The `LLMService` catches this to fall back to the deterministic client
    rather than crashing the agent graph.
    """


class LLMClient(Protocol):
    """Two-method contract used by the agent nodes.

    Implementations MUST be deterministic in failure mode: never raise on
    invalid input — raise `LLMError` only for upstream/transport failures.
    Argument validation should happen before reaching the client.
    """

    def classify_intent(self, *, message: str) -> IntentClassification:
        """Classify the user's latest message into an intent + tool hints."""
        ...

    def synthesize_decision(
        self,
        *,
        intent: str,
        recommendation: str,
        evidence: list[dict],
        deterministic_reasoning: list[str],
    ) -> DecisionSynthesis:
        """Produce a richer reasoning trace from gathered evidence."""
        ...
