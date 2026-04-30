"""Serper (Google Search API) client.

Calls ``POST https://google.serper.dev/search`` and normalizes the
``organic`` array into our `SearchResponse` shape. All provider-side
failures are surfaced as `SearchError` so the service layer can fall
back deterministically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from alphalens.core.logging import get_logger
from alphalens.integrations.search.base import SearchClient, SearchError
from alphalens.schemas.search import SearchResponse, SearchResult

logger = get_logger(__name__)

PROVIDER_NAME = "serper"
DEFAULT_BASE_URL = "https://google.serper.dev/search"


class SerperSearchClient(SearchClient):
    """Thin adapter over the Serper /search endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None,
        timeout_seconds: float = 10.0,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise SearchError("Serper API key is not configured.")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._base_url = base_url
        self._client = client  # injected client owns its own lifecycle.

    def search(self, query: str, k: int = 5) -> SearchResponse:
        normalized = (query or "").strip()
        if not normalized:
            raise SearchError("Search query must be non-empty.")
        if k <= 0:
            return SearchResponse(query=normalized, results=[], provider=PROVIDER_NAME)

        payload = self._fetch(normalized, k=k)
        return _parse_response(payload, query=normalized)

    def _fetch(self, query: str, *, k: int) -> dict[str, Any]:
        headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }
        body = {"q": query, "num": k}
        try:
            if self._client is not None:
                response = self._client.post(
                    self._base_url, headers=headers, json=body
                )
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        self._base_url, headers=headers, json=body
                    )
        except httpx.TimeoutException as exc:
            raise SearchError(f"Serper timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise SearchError(f"Serper transport error: {exc}") from exc

        if response.status_code == 429:
            raise SearchError("Serper rate-limited (HTTP 429).")
        if response.status_code != 200:
            raise SearchError(
                f"Serper HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchError(f"Serper returned non-JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise SearchError("Serper returned unexpected payload type.")
        return payload


def _parse_response(payload: dict[str, Any], *, query: str) -> SearchResponse:
    organic = payload.get("organic")
    if organic is None:
        # No `organic` key: treat as zero-result rather than malformed
        # provided the payload is otherwise a dict.
        return SearchResponse(query=query, results=[], provider=PROVIDER_NAME)
    if not isinstance(organic, list):
        raise SearchError("Serper 'organic' field is not a list.")

    results: list[SearchResult] = []
    for item in organic:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_item(item)
        if normalized is None:
            continue
        results.append(normalized)
    return SearchResponse(query=query, results=results, provider=PROVIDER_NAME)


def _normalize_item(item: dict[str, Any]) -> SearchResult | None:
    url = item.get("link") or item.get("url")
    title = item.get("title")
    if not url or not title:
        return None
    snippet = str(item.get("snippet") or "")
    source = _source_from_url(str(url))
    published_at = _parse_date(item.get("date"))
    try:
        return SearchResult(
            title=str(title),
            url=str(url),  # type: ignore[arg-type]
            snippet=snippet,
            source=source,
            published_at=published_at,
            provider=PROVIDER_NAME,
        )
    except ValidationError as exc:
        logger.debug("serper_item_skipped", error=str(exc), url=url)
        return None


def _source_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc or "web"
    except ValueError:
        return "web"
    return host.removeprefix("www.") or "web"


def _parse_date(raw: Any) -> datetime | None:
    if not raw:
        return None
    text = str(raw)
    # Serper sometimes returns ISO timestamps and sometimes loose strings
    # like "2 days ago". Only try strict ISO parsing; everything else is
    # surfaced as `None` so we don't fabricate dates.
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
