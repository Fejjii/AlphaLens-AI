"""OpenAI-backed LLM client.

Uses the SDK's structured-output parsing so the model is forced to return
JSON conforming to our Pydantic schemas. Any transport, parsing, or
validation failure is surfaced as `LLMError` so the service layer can fall
back deterministically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alphalens.core.logging import get_logger
from alphalens.integrations.llm.base import LLMClient, LLMError
from alphalens.schemas.llm import DecisionSynthesis, IntentClassification, RouteClassification

if TYPE_CHECKING:  # pragma: no cover - import only for typing
    from openai import OpenAI

logger = get_logger(__name__)


_INTENT_SYSTEM_PROMPT = (
    "You are the routing layer of an investment-research agent. "
    "Classify the user's latest message into one of: "
    "portfolio_performance, policy_breach_check, risk_review, rag_policy_question, "
    "investment_recommendation, market_news_question, sec_filings_question, "
    "macro_question, general_question. "
    "Extract any equity tickers mentioned (uppercase, 1-5 letters). "
    "Set the needs_* flags to indicate which tools should be consulted. "
    "Be conservative: only set a flag when the message clearly calls for "
    "that capability."
)

_ROUTER_SYSTEM_PROMPT = (
    "You are the domain router for AlphaLens AI (portfolio / investment workflows). "
    "Fill every schema field. answer_type rules: "
    "investment_decision ONLY when the user requests analysis, retrieval, comparison, recommendation, "
    "or explanation grounded in portfolios, holdings, tickers, risk, policy/mandate, RAG/internal docs, "
    "market or news context for investments, macro in an investing frame, SEC filings, performance, "
    "or workflow actions like buy/sell/trim/rebalance/hold/escalate. "
    "app_help for questions about the product itself: languages, speech, capabilities, what you can do, "
    "tools list, how AlphaLens works, how to upload, how reports/scenarios/approvals features work — "
    "not a live portfolio approval decision. "
    "out_of_scope for topics unrelated to investing, finance workflows, or this app (weather, recipes, sports, medical, legal advice, trivia). "
    "clarification when the prompt is too vague and there is no clear investment subject (e.g. pronouns, 'should I do it?') "
    "unless the user message clearly continues a concrete investment thread. "
    "Be conservative: if unsure, prefer clarification over investment_decision. "
    "Apply the same classification for English, French, German, and Arabic input. "
    "suggested_tools: only when answer_type is investment_decision, choose zero or more from "
    "rag_retrieve, web_search, market_quote, macro_snapshot, sec_filings, portfolio_analyze, risk_check "
    "(use aliases rag_retriever→rag_retrieve, web_news→web_search). Otherwise return an empty list. "
    "confidence must reflect certainty; use low values when ambiguous."
)

_SYNTHESIS_SYSTEM_PROMPT = (
    "You are a portfolio analyst summarising tool evidence into a concise "
    "reasoning trace for a human reviewer. Stay grounded in the evidence "
    "provided; do not invent numbers. Each reasoning bullet should be one "
    "short sentence. Do not paste raw knowledge-base filenames, long "
    "snippets, or bullet lists of sources—refer generically (e.g. internal "
    "policy documents, portfolio snapshot). The summary must be one paragraph. "
    "Optionally suggest a small confidence adjustment in [-0.3, +0.3] if the "
    "evidence is unusually strong or weak; otherwise leave it null."
)


class OpenAILLMClient(LLMClient):
    """Thin adapter around `openai.OpenAI` with structured outputs."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float,
        top_p: float,
        client: OpenAI | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        if client is not None:
            self._client = client
        else:
            try:
                from openai import OpenAI  # local import keeps openai optional
            except ImportError as exc:  # pragma: no cover - defensive
                raise LLMError("openai package is not installed") from exc
            self._client = OpenAI(api_key=api_key)

    def classify_intent(self, *, message: str) -> IntentClassification:
        return self._parse(
            schema=IntentClassification,
            system_prompt=_INTENT_SYSTEM_PROMPT,
            user_payload={"message": message},
        )

    def classify_route(self, *, message: str) -> RouteClassification:
        return self._parse(
            schema=RouteClassification,
            system_prompt=_ROUTER_SYSTEM_PROMPT,
            user_payload={"user_message": message},
        )

    def synthesize_decision(
        self,
        *,
        intent: str,
        recommendation: str,
        evidence: list[dict],
        deterministic_reasoning: list[str],
    ) -> DecisionSynthesis:
        return self._parse(
            schema=DecisionSynthesis,
            system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
            user_payload={
                "intent": intent,
                "recommendation": recommendation,
                "evidence": evidence,
                "baseline_reasoning": deterministic_reasoning,
            },
        )

    def _parse(
        self,
        *,
        schema: type,
        system_prompt: str,
        user_payload: dict[str, Any],
    ) -> Any:
        try:
            completion = self._client.beta.chat.completions.parse(
                model=self._model,
                temperature=self._temperature,
                top_p=self._top_p,
                response_format=schema,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": _to_user_content(user_payload)},
                ],
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises a wide variety
            logger.warning("openai_call_failed", error=str(exc), schema=schema.__name__)
            raise LLMError(f"OpenAI call failed: {exc}") from exc

        parsed = completion.choices[0].message.parsed if completion.choices else None
        if parsed is None:
            logger.warning("openai_parse_empty", schema=schema.__name__)
            raise LLMError("OpenAI returned no parsed output")
        return parsed


def _to_user_content(payload: dict[str, Any]) -> str:
    import json

    # Compact JSON; the model is expected to read structured input verbatim.
    return json.dumps(payload, default=str, ensure_ascii=False)
