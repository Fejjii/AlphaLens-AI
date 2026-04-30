"""LLM service: picks an `LLMClient` and falls back deterministically.

Selection rule:

    if settings.openai_api_key and settings.llm_enabled -> OpenAILLMClient
    else                                                 -> DeterministicFallbackLLMClient

When the primary client raises ``LLMError`` we log and fall through to the
deterministic client so the agent never crashes on transient API issues.

Usage events are emitted via an optional ``UsageService``.  When none is
injected the service is a no-op so all call sites stay identical.
"""

from __future__ import annotations

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger
from alphalens.infrastructure.observability.langsmith import trace_llm_call
from alphalens.integrations.llm import (
    DeterministicFallbackLLMClient,
    LLMClient,
    LLMError,
    OpenAILLMClient,
)
from alphalens.schemas.llm import DecisionSynthesis, IntentClassification

logger = get_logger(__name__)


class LLMService:
    """Wraps a primary client and a deterministic fallback."""

    def __init__(
        self,
        *,
        primary: LLMClient | None,
        fallback: LLMClient,
        model: str | None = None,
        usage_service: object | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._model = model
        # Weak reference to avoid circular imports; duck-typed against
        # UsageService so tests can inject lightweight fakes.
        self._usage = usage_service

    @property
    def using_llm(self) -> bool:
        """True when an LLM-backed primary is configured."""
        return self._primary is not None

    def classify_intent(
        self,
        *,
        message: str,
        conversation_id: str | None = None,
    ) -> IntentClassification:
        meta = {"conversation_id": conversation_id, "input": message}
        with trace_llm_call("classify_intent", metadata=meta):
            if self._primary is None:
                self._record_fallback("classify_intent", conversation_id)
                return self._fallback.classify_intent(message=message)
            try:
                result = self._primary.classify_intent(message=message)
                self._record_llm("classify_intent", conversation_id)
                return result
            except LLMError as exc:
                logger.warning(
                    "llm_classify_intent_fallback", error=str(exc), reason="llm_error"
                )
                self._record_fallback("classify_intent", conversation_id)
                return self._fallback.classify_intent(message=message)

    def synthesize_decision(
        self,
        *,
        intent: str,
        recommendation: str,
        evidence: list[dict],
        deterministic_reasoning: list[str],
        conversation_id: str | None = None,
    ) -> DecisionSynthesis:
        meta = {"conversation_id": conversation_id, "intent": intent}
        with trace_llm_call("synthesize_decision", metadata=meta):
            if self._primary is None:
                self._record_fallback("synthesize_decision", conversation_id)
                return self._fallback.synthesize_decision(
                    intent=intent,
                    recommendation=recommendation,
                    evidence=evidence,
                    deterministic_reasoning=deterministic_reasoning,
                )
            try:
                result = self._primary.synthesize_decision(
                    intent=intent,
                    recommendation=recommendation,
                    evidence=evidence,
                    deterministic_reasoning=deterministic_reasoning,
                )
                self._record_llm("synthesize_decision", conversation_id)
                return result
            except LLMError as exc:
                logger.warning(
                    "llm_synthesize_fallback", error=str(exc), reason="llm_error"
                )
                self._record_fallback("synthesize_decision", conversation_id)
                return self._fallback.synthesize_decision(
                    intent=intent,
                    recommendation=recommendation,
                    evidence=evidence,
                    deterministic_reasoning=deterministic_reasoning,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_llm(self, operation: str, conversation_id: str | None) -> None:
        if self._usage is None:
            return
        try:
            self._usage.record_llm_usage(
                event_type="llm_call",
                provider="openai",
                model=self._model,
                conversation_id=conversation_id,
                metadata={"operation": operation},
            )
        except Exception:  # noqa: BLE001 - never let tracking break the agent
            pass

    def _record_fallback(self, operation: str, conversation_id: str | None) -> None:
        if self._usage is None:
            return
        try:
            self._usage.record_llm_usage(
                event_type="llm_fallback",
                provider="fallback",
                model=None,
                input_tokens=0,
                output_tokens=0,
                conversation_id=conversation_id,
                metadata={"operation": operation},
            )
        except Exception:  # noqa: BLE001
            pass


def get_llm_client(settings: Settings) -> LLMClient | None:
    """Build the primary LLM client, or None when LLM mode is disabled."""

    if not settings.llm_enabled or not settings.openai_api_key:
        return None
    try:
        return OpenAILLMClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            top_p=settings.openai_top_p,
        )
    except LLMError as exc:
        logger.warning("llm_client_init_failed", error=str(exc))
        return None


def get_llm_service(
    settings: Settings,
    usage_service: object | None = None,
) -> LLMService:
    return LLMService(
        primary=get_llm_client(settings),
        fallback=DeterministicFallbackLLMClient(),
        model=settings.openai_model,
        usage_service=usage_service,
    )
