"""Schemas for web/news search integrations.

Normalized cross-provider shapes so downstream code (agent, tool) stays
provider-agnostic.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, HttpUrl

from alphalens.schemas.common import APIModel


class SearchResult(APIModel):
    """A single search result, normalized across providers."""

    title: str = Field(..., min_length=1, max_length=512)
    url: HttpUrl
    snippet: str = Field(default="", max_length=2000)
    source: str = Field(..., min_length=1, max_length=128)
    published_at: datetime | None = None
    provider: str = Field(..., min_length=1, max_length=64)


class SearchResponse(APIModel):
    """A list of results for a query, plus the provider that produced them."""

    query: str = Field(..., min_length=1, max_length=512)
    results: list[SearchResult] = Field(default_factory=list)
    provider: str = Field(..., min_length=1, max_length=64)
    fallback_used: bool = False
    provider_source: str = Field(default="primary", min_length=1, max_length=64)
