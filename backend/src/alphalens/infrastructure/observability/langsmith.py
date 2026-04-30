"""LangSmith observability initialisation and tracing helpers.

Tracing is entirely optional. When ``LANGCHAIN_TRACING_V2`` is false, or
``LANGCHAIN_API_KEY`` is absent, every public function in this module is a
no-op and imposes no runtime overhead.

Usage
-----
Call ``setup_langsmith(settings)`` once at application startup. After that,
wrap LLM calls with ``trace_llm_call`` and agent nodes with ``trace_node``.
Both wrappers fall through transparently when tracing is disabled.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Generator, TypeVar

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Module-level sentinel so callers can cheaply guard wrapping logic.
_tracing_active: bool = False


def setup_langsmith(settings: Settings) -> None:
    """Configure LangSmith tracing from *settings*.

    Sets the three environment variables LangChain/LangSmith read at import
    time. Safe to call multiple times (idempotent when settings are unchanged).
    Has no effect — and emits no warnings — when tracing is disabled.
    """
    global _tracing_active

    if not settings.langsmith_enabled:
        _tracing_active = False
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key  # type: ignore[assignment]
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

    _tracing_active = True
    logger.info(
        "langsmith_tracing_enabled",
        project=settings.langchain_project,
    )


def is_tracing_active() -> bool:
    """Return True when LangSmith tracing has been successfully initialised."""
    return _tracing_active


@contextmanager
def trace_llm_call(
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> Generator[None, None, None]:
    """Context manager that wraps an LLM call in a LangSmith span.

    Falls through without any LangSmith import when tracing is disabled.

    Args:
        name: Human-readable span name (e.g. ``"classify_intent"``).
        metadata: Arbitrary key/value pairs attached to the span.
    """
    if not _tracing_active:
        yield
        return

    try:
        from langsmith import trace  # type: ignore[import-untyped]

        with trace(name, metadata=metadata or {}):
            yield
    except Exception:  # noqa: BLE001 – never let tracing break the agent
        yield


@contextmanager
def trace_node(
    node_name: str,
    *,
    inputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[None, None, None]:
    """Context manager that wraps a LangGraph node in a LangSmith span.

    Args:
        node_name: One of ``interpret``, ``gather``, ``synthesize``, ``decide``.
        inputs: Snapshot of relevant state fields passed into this node.
        metadata: Arbitrary extra context (conversation_id, intent, tickers…).
    """
    if not _tracing_active:
        yield
        return

    combined = {**(metadata or {}), "node": node_name, "inputs": inputs or {}}
    try:
        from langsmith import trace  # type: ignore[import-untyped]

        with trace(f"node:{node_name}", metadata=combined):
            yield
    except Exception:  # noqa: BLE001 – never let tracing break the agent
        yield


def trace_tool_call(
    tool_name: str,
    inputs: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a tool invocation as trace metadata (fire-and-forget).

    This does not open a span — it is meant to be called inside an existing
    ``trace_node`` context so the tool call appears as a child event.

    Args:
        tool_name: Registry key of the tool (e.g. ``"market_quote"``).
        inputs: Kwargs passed to the tool.
        metadata: Additional context (conversation_id, intent, tickers…).
    """
    if not _tracing_active:
        return

    try:
        from langsmith import get_current_run_tree  # type: ignore[import-untyped]

        run = get_current_run_tree()
        if run is not None:
            run.add_metadata(
                {
                    "tool_call": {
                        "name": tool_name,
                        "inputs": inputs,
                        **(metadata or {}),
                    }
                }
            )
    except Exception:  # noqa: BLE001
        pass
