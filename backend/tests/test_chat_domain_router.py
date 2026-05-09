from __future__ import annotations

import pytest

from alphalens.core.config import get_settings
from alphalens.schemas.agent import ChatAnswerType
from alphalens.schemas.llm import RouteClassification
from alphalens.services.chat_domain_router import resolve_chat_route


def _resolve(text: str, *, prior: list | None = None) -> str:
    r = resolve_chat_route(
        text,
        prior_messages=prior or [],
        detected_language="en",
        confidence_threshold=get_settings().chat_router_confidence_threshold,
        llm_classify=None,
    )
    return r.answer_type


@pytest.mark.parametrize(
    "phrase",
    [
        "How many languages do you support?",
        "Can I speak to you in French?",
        "Do you handle German prompts?",
        "Which languages work for speech?",
        "What can you do in AlphaLens?",
        "What tools are available here?",
        "How do approvals work?",
        "How does RAG work here?",
    ],
)
def test_app_help_paraphrases(phrase: str) -> None:
    assert _resolve(phrase) == ChatAnswerType.APP_HELP.value
    r = resolve_chat_route(
        phrase,
        prior_messages=[],
        detected_language="en",
        confidence_threshold=get_settings().chat_router_confidence_threshold,
        llm_classify=None,
    )
    assert r.suggested_tools == []


@pytest.mark.parametrize(
    "phrase",
    [
        "What is the weather tomorrow?",
        "Give me a pasta recipe.",
        "Who won the football game?",
    ],
)
def test_out_of_scope_paraphrases(phrase: str) -> None:
    assert _resolve(phrase) == ChatAnswerType.OUT_OF_SCOPE.value
    r = resolve_chat_route(
        phrase,
        prior_messages=[],
        detected_language="en",
        confidence_threshold=get_settings().chat_router_confidence_threshold,
        llm_classify=None,
    )
    assert r.suggested_tools == []


@pytest.mark.parametrize(
    "phrase",
    [
        "Are we too concentrated in Microsoft?",
        "Do we breach the mandate?",
        "Is NVDA above our risk limit?",
        "How did the portfolio perform last month?",
        "What happened to NVDA today?",
        "What does our policy say about concentration?",
    ],
)
def test_investment_paraphrases(phrase: str) -> None:
    assert _resolve(phrase) == ChatAnswerType.INVESTMENT_DECISION.value


def test_rag_inference_suggested_tools() -> None:
    r = resolve_chat_route(
        "What does the internal policy say about single-name concentration?",
        prior_messages=[],
        detected_language="en",
        confidence_threshold=get_settings().chat_router_confidence_threshold,
        llm_classify=None,
    )
    assert r.answer_type == ChatAnswerType.INVESTMENT_DECISION.value
    assert "rag_retrieve" in r.suggested_tools


def test_web_news_inference() -> None:
    r = resolve_chat_route(
        "Why is NVDA moving today?",
        prior_messages=[],
        detected_language="en",
        confidence_threshold=get_settings().chat_router_confidence_threshold,
        llm_classify=None,
    )
    assert r.answer_type == ChatAnswerType.INVESTMENT_DECISION.value
    assert "web_search" in r.suggested_tools


def test_sec_inference() -> None:
    r = resolve_chat_route(
        "What does the latest 10-K say about NVDA risks?",
        prior_messages=[],
        detected_language="en",
        confidence_threshold=get_settings().chat_router_confidence_threshold,
        llm_classify=None,
    )
    assert r.answer_type == ChatAnswerType.INVESTMENT_DECISION.value
    assert "sec_filings" in r.suggested_tools


def test_macro_inference() -> None:
    r = resolve_chat_route(
        "How would higher rates affect the portfolio?",
        prior_messages=[],
        detected_language="en",
        confidence_threshold=get_settings().chat_router_confidence_threshold,
        llm_classify=None,
    )
    assert r.answer_type == ChatAnswerType.INVESTMENT_DECISION.value
    assert "macro_snapshot" in r.suggested_tools


def test_clarification_without_investment_context() -> None:
    assert _resolve("Should I do it?") == ChatAnswerType.CLARIFICATION.value
    assert _resolve("What about this?") == ChatAnswerType.CLARIFICATION.value


def test_clarification_continues_when_investment_context_present() -> None:
    prior = [
        {"role": "user", "content": "Let's discuss NVDA risk."},
        {"role": "assistant", "content": "NVDA is a key position."},
    ]
    r = resolve_chat_route(
        "Should I trim it?",
        prior_messages=prior,
        detected_language="en",
        confidence_threshold=get_settings().chat_router_confidence_threshold,
        llm_classify=None,
    )
    assert r.answer_type == ChatAnswerType.INVESTMENT_DECISION.value


def test_llm_low_confidence_becomes_clarification() -> None:
    def fake_llm(_msg: str) -> RouteClassification:
        return RouteClassification(
            answer_type="investment_decision",
            intent="portfolio_performance",
            confidence=0.2,
            language="en",
            reason="uncertain",
            suggested_tools=["portfolio_analyze"],
        )

    r = resolve_chat_route(
        "Some vague message",
        prior_messages=[],
        detected_language="en",
        confidence_threshold=0.62,
        llm_classify=fake_llm,
    )
    assert r.answer_type == ChatAnswerType.CLARIFICATION.value
    assert r.router_source == "llm_low_confidence"


def test_llm_router_used_when_primary_returns_high_confidence() -> None:
    def fake_llm(_msg: str) -> RouteClassification:
        return RouteClassification(
            answer_type="app_help",
            intent="app_capability",
            confidence=0.95,
            language="en",
            reason="languages",
            suggested_tools=[],
        )

    r = resolve_chat_route(
        "Random offline phrase with no deterministic cue",
        prior_messages=[],
        detected_language="en",
        confidence_threshold=0.62,
        llm_classify=fake_llm,
    )
    assert r.answer_type == ChatAnswerType.APP_HELP.value
    assert r.router_source == "llm"
