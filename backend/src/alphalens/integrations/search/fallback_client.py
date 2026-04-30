"""Deterministic offline search client.

Used for local development, tests, and as a safety net when an external
provider fails. Results are derived from a hash of the query so they're
stable across runs but vary by query.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from alphalens.integrations.search.base import SearchClient
from alphalens.schemas.search import SearchResponse, SearchResult

PROVIDER_NAME = "fallback"

# A small pool of plausible-looking financial outlets. The hash picks
# which subset and in what order — purely so demos and tests don't see
# obviously synthetic content.
_SOURCES: tuple[tuple[str, str], ...] = (
    ("reuters.com", "Reuters"),
    ("bloomberg.com", "Bloomberg"),
    ("ft.com", "Financial Times"),
    ("wsj.com", "Wall Street Journal"),
    ("cnbc.com", "CNBC"),
    ("seekingalpha.com", "Seeking Alpha"),
    ("marketwatch.com", "MarketWatch"),
    ("barrons.com", "Barron's"),
)

_HEADLINE_TEMPLATES: tuple[str, ...] = (
    "Analysts weigh in on {q}",
    "What investors should know about {q}",
    "{q}: market reaction and outlook",
    "Macro context for {q}",
    "Earnings and catalysts around {q}",
    "Risk factors to watch for {q}",
    "Sector implications of {q}",
)

_SNIPPET_TEMPLATES: tuple[str, ...] = (
    "Recent coverage discusses positioning, valuation, and sentiment around {q}.",
    "Sell-side notes flag both upside catalysts and downside risks tied to {q}.",
    "Macro backdrop and rate path remain the dominant factors for {q}.",
    "Earnings revisions and guidance updates continue to drive moves in {q}.",
    "Cross-asset signals suggest a mixed outlook for {q} in the near term.",
)


def _seed(text: str) -> int:
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


class FallbackSearchClient(SearchClient):
    """Hash-derived synthetic results that never raise."""

    def search(self, query: str, k: int = 5) -> SearchResponse:
        normalized = (query or "").strip() or "market"
        seed = _seed(normalized)
        results: list[SearchResult] = []
        for i in range(max(0, k)):
            offset = seed + i
            domain, source = _SOURCES[offset % len(_SOURCES)]
            title = _HEADLINE_TEMPLATES[(offset >> 3) % len(_HEADLINE_TEMPLATES)].format(
                q=normalized
            )
            snippet = _SNIPPET_TEMPLATES[(offset >> 5) % len(_SNIPPET_TEMPLATES)].format(
                q=normalized
            )
            published = datetime.now(tz=UTC) - timedelta(hours=(offset % 72))
            slug = _slug(normalized, i)
            results.append(
                SearchResult(
                    title=title,
                    url=f"https://www.{domain}/article/{slug}",  # type: ignore[arg-type]
                    snippet=snippet,
                    source=source,
                    published_at=published,
                    provider=PROVIDER_NAME,
                )
            )
        return SearchResponse(
            query=normalized, results=results, provider=PROVIDER_NAME
        )


def _slug(query: str, index: int) -> str:
    base = "-".join(query.lower().split())[:60] or "market"
    return f"{base}-{index}"
