"""Web/news search tool.

Thin wrapper around `SearchService`. Output payload:

    {
        "provider": "serper" | "fallback",
        "query": "...",
        "results": [
            {
                "title": "...",
                "url": "...",
                "snippet": "...",
                "source": "...",
                "published_at": "<iso8601>" | None,
                "provider": "...",
            },
            ...
        ],
    }
"""

from __future__ import annotations

from alphalens.schemas.search import SearchResponse, SearchResult
from alphalens.services.search_service import DEFAULT_K, SearchService
from alphalens.tools.registry import Tool, ToolResult


def make_web_search_tool(service: SearchService, *, default_k: int = DEFAULT_K) -> Tool:
    def _run(query: str, k: int = default_k) -> ToolResult:
        normalized = (query or "").strip()
        if not normalized:
            empty = SearchResponse(
                query="", results=[], provider="fallback"
            )
            return _response_to_result(empty, summary_prefix="No query provided.")
        response = service.search(normalized, k=k)
        return _response_to_result(response)

    return Tool(
        name="web_search",
        description=(
            "Search the public web for recent news/market context for a query. "
            "Returns up to k normalized results."
        ),
        func=_run,
        parameters={
            "query": "Free-text search query",
            "k": "Maximum number of results (default 5)",
        },
    )


def _response_to_result(
    response: SearchResponse, *, summary_prefix: str | None = None
) -> ToolResult:
    if not response.results:
        summary = summary_prefix or f"No web results for: {response.query!r}."
    else:
        sources = ", ".join(sorted({r.source for r in response.results}))
        summary = f"Retrieved {len(response.results)} web result(s) from {sources}."
    return ToolResult(
        name="web_search",
        summary=summary,
        data={
            "provider": response.provider,
            "fallback_used": response.fallback_used,
            "provider_source": response.provider_source,
            "query": response.query,
            "results": [_result_to_dict(r) for r in response.results],
        },
    )


def _result_to_dict(result: SearchResult) -> dict:
    return {
        "title": result.title,
        "url": str(result.url),
        "snippet": result.snippet,
        "source": result.source,
        "published_at": result.published_at.isoformat() if result.published_at else None,
        "provider": result.provider,
    }
