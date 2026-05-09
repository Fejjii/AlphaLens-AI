from __future__ import annotations

from alphalens.services.domain_gate import ChatAnswerDomain, classify_chat_domain


def test_french_capability_question_is_app_help() -> None:
    text = "Est ce que tu comprends en français ? Est ce que tu me comprends en français ?"
    assert classify_chat_domain(text) == ChatAnswerDomain.APP_HELP_OR_CAPABILITY


def test_weather_question_is_out_of_scope() -> None:
    assert classify_chat_domain("What is the weather tomorrow?") == ChatAnswerDomain.OUT_OF_SCOPE_GENERAL


def test_portfolio_performance_is_investment() -> None:
    assert (
        classify_chat_domain("What has been the performance of the portfolio in the last 1 month?")
        == ChatAnswerDomain.INVESTMENT_AGENT_TASK
    )


def test_rag_policy_question_is_investment() -> None:
    assert (
        classify_chat_domain(
            "Use RAG and internal policy documents to explain whether NVDA should be trimmed."
        )
        == ChatAnswerDomain.INVESTMENT_AGENT_TASK
    )


def test_portfolio_weather_combo_prefers_investment() -> None:
    assert (
        classify_chat_domain("Weather and my portfolio risk together?")
        == ChatAnswerDomain.INVESTMENT_AGENT_TASK
    )


def test_short_follow_up_routes_investment_when_thread_has_history() -> None:
    prior = [
        {"role": "user", "content": "Let's discuss NVDA."},
        {"role": "assistant", "content": "Echo: ok"},
    ]
    assert (
        classify_chat_domain("What about tomorrow?", prior_messages=prior)
        == ChatAnswerDomain.INVESTMENT_AGENT_TASK
    )


def test_ambiguous_short_question_is_clarification_bucket_without_history() -> None:
    """Clarification maps to the legacy 'app/help' bucket (no investment graph)."""
    assert classify_chat_domain("What about tomorrow?") == ChatAnswerDomain.APP_HELP_OR_CAPABILITY
