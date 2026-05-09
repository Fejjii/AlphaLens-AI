"""RAG retrieval tool.

Thin wrapper over `RAGService.get_relevant_context` so the agent can call
it through the standard tool interface.
"""

from __future__ import annotations

from dataclasses import asdict

from alphalens.services.rag_service import RAGService
from alphalens.tools.registry import Tool, ToolResult

DEFAULT_K = 4


def make_rag_tool(rag_service: RAGService, *, k: int = DEFAULT_K) -> Tool:
    def _run(query: str) -> ToolResult:
        chunks = rag_service.get_relevant_context(query, k=k)
        if not chunks:
            summary = f"No knowledge-base context found for: {query!r}."
        else:
            summary = f"Retrieved {len(chunks)} passage(s) from the internal knowledge base."
        return ToolResult(
            name="rag_retrieve",
            summary=summary,
            data={"query": query, "chunks": [asdict(c) for c in chunks]},
        )

    return Tool(
        name="rag_retrieve",
        description="Retrieve top-k passages from the internal knowledge base for a query.",
        func=_run,
        parameters={"query": "Free-text query string"},
    )
