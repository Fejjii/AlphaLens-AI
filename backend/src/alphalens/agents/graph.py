"""LangGraph graph builder.

Wires the four nodes:

    START -> interpret -> gather -> synthesize -> decide -> END

The graph is parameterized by a `ToolRegistry` (for deterministic tool
execution) and an `LLMService` (for intent classification and reasoning
synthesis, with a deterministic fallback).
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from alphalens.agents.nodes import (
    decide_node,
    make_gather_node,
    make_interpret_node,
    make_synthesize_node,
)
from alphalens.agents.state import AgentState
from alphalens.integrations.llm import DeterministicFallbackLLMClient
from alphalens.services.llm_service import LLMService
from alphalens.tools.registry import ToolRegistry


def build_graph(
    registry: ToolRegistry,
    llm_service: LLMService | None = None,
    *,
    checkpointer: Any | None = None,
) -> CompiledStateGraph:
    llm = llm_service or LLMService(
        primary=None, fallback=DeterministicFallbackLLMClient()
    )
    builder: StateGraph = StateGraph(AgentState)
    builder.add_node("interpret", make_interpret_node(llm))
    builder.add_node("gather", make_gather_node(registry))
    builder.add_node("synthesize", make_synthesize_node(llm))
    builder.add_node("decide", decide_node)
    builder.add_edge(START, "interpret")
    builder.add_edge("interpret", "gather")
    builder.add_edge("gather", "synthesize")
    builder.add_edge("synthesize", "decide")
    builder.add_edge("decide", END)
    return builder.compile(checkpointer=checkpointer)
