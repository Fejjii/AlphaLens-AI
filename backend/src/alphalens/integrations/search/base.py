"""Protocol for web/news search clients."""

from __future__ import annotations

from typing import Protocol

from alphalens.schemas.search import SearchResponse


class SearchError(Exception):
    """Raised by a `SearchClient` for any provider-side failure.

    Includes: missing API key, malformed payload, rate limits, transport
    errors, and timeouts. The service layer catches this to fall back to
    the deterministic client rather than crashing the agent.
    """


class SearchClient(Protocol):
    """Single-method contract used by the search service."""

    def search(self, query: str, k: int = 5) -> SearchResponse:
        """Return up to `k` results for `query`.

        Raises `SearchError` on any provider-side failure.
        """
        ...
