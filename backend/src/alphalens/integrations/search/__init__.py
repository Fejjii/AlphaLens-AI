"""Web/news search clients used by the agent and tooling."""

from alphalens.integrations.search.base import SearchClient, SearchError
from alphalens.integrations.search.fallback_client import FallbackSearchClient
from alphalens.integrations.search.serper_client import SerperSearchClient

__all__ = [
    "FallbackSearchClient",
    "SearchClient",
    "SearchError",
    "SerperSearchClient",
]
