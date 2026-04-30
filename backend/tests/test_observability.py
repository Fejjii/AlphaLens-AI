"""Tests for LangSmith observability integration.

All tests must pass without a real LangSmith API key — tracing is a no-op
when ``LANGCHAIN_TRACING_V2`` is false or the key is absent.
"""

from __future__ import annotations

import os

import pytest

from alphalens.core.config import Settings
from alphalens.infrastructure.observability import langsmith as ls_module
from alphalens.infrastructure.observability.langsmith import (
    is_tracing_active,
    setup_langsmith,
    trace_llm_call,
    trace_node,
    trace_tool_call,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_langsmith_env() -> None:
    for key in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"):
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def reset_tracing_state():
    """Ensure tracing state is reset around each test."""
    _clear_langsmith_env()
    ls_module._tracing_active = False
    yield
    ls_module._tracing_active = False
    _clear_langsmith_env()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_langsmith_disabled_by_default() -> None:
    settings = Settings()
    assert settings.langchain_tracing_v2 is False
    assert settings.langchain_api_key is None
    assert settings.langchain_project == "AlphaLens AI"
    assert settings.langsmith_enabled is False


def test_langsmith_enabled_when_both_fields_set() -> None:
    settings = Settings(
        LANGCHAIN_TRACING_V2=True,
        LANGCHAIN_API_KEY="ls-test-key",
        LANGCHAIN_PROJECT="MyProject",
    )
    assert settings.langsmith_enabled is True
    assert settings.langchain_project == "MyProject"


def test_langsmith_disabled_when_key_missing() -> None:
    settings = Settings(LANGCHAIN_TRACING_V2=True, LANGCHAIN_API_KEY=None)
    assert settings.langsmith_enabled is False


def test_langsmith_disabled_when_flag_false_with_key() -> None:
    settings = Settings(LANGCHAIN_TRACING_V2=False, LANGCHAIN_API_KEY="ls-test-key")
    assert settings.langsmith_enabled is False


# ---------------------------------------------------------------------------
# setup_langsmith
# ---------------------------------------------------------------------------


def test_setup_langsmith_no_op_when_disabled() -> None:
    settings = Settings()
    setup_langsmith(settings)

    assert is_tracing_active() is False
    assert os.environ.get("LANGCHAIN_TRACING_V2") is None


def test_setup_langsmith_sets_env_vars_when_enabled() -> None:
    settings = Settings(
        LANGCHAIN_TRACING_V2=True,
        LANGCHAIN_API_KEY="ls-fake-key",
        LANGCHAIN_PROJECT="TestProject",
    )
    setup_langsmith(settings)

    assert is_tracing_active() is True
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "ls-fake-key"
    assert os.environ["LANGCHAIN_PROJECT"] == "TestProject"


def test_setup_langsmith_is_idempotent() -> None:
    settings = Settings(
        LANGCHAIN_TRACING_V2=True,
        LANGCHAIN_API_KEY="ls-fake-key",
    )
    setup_langsmith(settings)
    setup_langsmith(settings)

    assert is_tracing_active() is True


def test_setup_langsmith_disables_when_called_with_disabled_settings() -> None:
    # First enable, then reconfigure to disabled.
    ls_module._tracing_active = True
    settings = Settings()
    setup_langsmith(settings)
    assert is_tracing_active() is False


# ---------------------------------------------------------------------------
# trace_llm_call — no-op when tracing is off
# ---------------------------------------------------------------------------


def test_trace_llm_call_noop_when_disabled() -> None:
    sentinel = []
    with trace_llm_call("classify_intent", metadata={"conversation_id": "x"}):
        sentinel.append(1)
    assert sentinel == [1], "body must execute even when tracing is disabled"


def test_trace_node_noop_when_disabled() -> None:
    sentinel = []
    with trace_node("interpret", inputs={"message": "hello"}, metadata={}):
        sentinel.append(1)
    assert sentinel == [1]


def test_trace_tool_call_noop_when_disabled() -> None:
    # Must not raise.
    trace_tool_call("market_quote", inputs={"tickers": ["AAPL"]}, metadata={})


# ---------------------------------------------------------------------------
# Wrappers remain transparent even if langsmith package is unavailable
# ---------------------------------------------------------------------------


def test_trace_llm_call_transparent_when_langsmith_missing(monkeypatch) -> None:
    """Simulate langsmith not being installed: import should not raise."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "langsmith":
            raise ImportError("no module named langsmith")
        return real_import(name, *args, **kwargs)

    ls_module._tracing_active = True
    monkeypatch.setattr(builtins, "__import__", fake_import)

    sentinel = []
    with trace_llm_call("test_op"):
        sentinel.append(1)

    assert sentinel == [1]


def test_trace_node_transparent_when_langsmith_missing(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "langsmith":
            raise ImportError("no module named langsmith")
        return real_import(name, *args, **kwargs)

    ls_module._tracing_active = True
    monkeypatch.setattr(builtins, "__import__", fake_import)

    sentinel = []
    with trace_node("gather", inputs={}):
        sentinel.append(1)

    assert sentinel == [1]


# ---------------------------------------------------------------------------
# Agent flow works end-to-end without LangSmith configured
# ---------------------------------------------------------------------------


def test_agent_nodes_work_without_langsmith(tmp_path) -> None:
    """Ensure the agent nodes run cleanly when tracing is disabled (default)."""
    from alphalens.agents.state import AgentState
    from alphalens.integrations.llm import DeterministicFallbackLLMClient
    from alphalens.agents.nodes import make_interpret_node, make_synthesize_node, decide_node
    from alphalens.services.llm_service import LLMService

    llm = LLMService(primary=None, fallback=DeterministicFallbackLLMClient())

    state: AgentState = {
        "messages": [{"role": "user", "content": "Show me my portfolio exposure."}]
    }

    interpret = make_interpret_node(llm)
    state = {**state, **interpret(state)}
    assert state["intent"] == "portfolio_review"

    synthesize = make_synthesize_node(llm)
    state = {**state, **synthesize(state)}
    assert state["reasoning"]

    state = {**state, **decide_node(state)}
    assert state["recommendation"]
