"""SEC filing service.

Selects the appropriate `SECClient` based on configuration:
- If SEC_PROVIDER == "sec_edgar": use SecEdgarClient.
- Otherwise: use FallbackSECClient.

If the live client fails at call time the service logs the error and
transparently retries with FallbackSECClient so the agent never errors
due to EDGAR unavailability.

Caching is optional and applied at the public method boundary. Filing
sections are particularly expensive (full-text fetch) and benefit most.
"""

from __future__ import annotations

import logging

from pydantic import TypeAdapter

from alphalens.core.config import Settings, get_settings
from alphalens.integrations.sec.base import SECError
from alphalens.integrations.sec.fallback_client import FallbackSECClient
from alphalens.integrations.sec.sec_edgar_client import SecEdgarClient
from alphalens.schemas.sec import FilingSearchResponse, FilingSection
from alphalens.services.cache_service import CacheService, build_cache_key

log = logging.getLogger(__name__)

_NAMESPACE = "sec"
_SECTIONS_ADAPTER = TypeAdapter(list[FilingSection])


class SECService:
    """Provider-aware SEC service with transparent fallback."""

    # Class-level default so tests that build the service via ``__new__``
    # (bypassing ``__init__``) still see a non-attribute-error cache slot.
    _cache: CacheService | None = None

    def __init__(
        self,
        settings: Settings,
        *,
        cache: CacheService | None = None,
    ) -> None:
        self._primary = _build_client(settings)
        self._fallback = FallbackSECClient()
        self._cache = cache

    def get_recent_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        limit: int = 3,
    ) -> FilingSearchResponse:
        key = build_cache_key(
            _NAMESPACE,
            {
                "op": "recent",
                "ticker": ticker.upper(),
                "form_types": sorted(form_types) if form_types else None,
                "limit": limit,
            },
        )
        if self._cache is not None:
            raw = self._cache.get_cached(key)
            if raw is not None:
                try:
                    return FilingSearchResponse.model_validate(raw)
                except Exception as exc:
                    log.warning("sec cache decode failed: %s", exc)
                    self._cache.delete(key)

        try:
            response = self._primary.get_recent_filings(
                ticker, form_types=form_types, limit=limit
            )
        except SECError as exc:
            log.warning("SECService: primary client failed (%s); using fallback.", exc)
            response = self._fallback.get_recent_filings(
                ticker, form_types=form_types, limit=limit
            )

        if self._cache is not None:
            self._cache.set_cached(key, response.model_dump(mode="json"))
        return response

    def get_filing_sections(
        self,
        ticker: str,
        form_type: str = "10-K",
    ) -> list[FilingSection]:
        key = build_cache_key(
            _NAMESPACE,
            {"op": "sections", "ticker": ticker.upper(), "form_type": form_type},
        )
        if self._cache is not None:
            raw = self._cache.get_cached(key)
            if isinstance(raw, list):
                try:
                    return _SECTIONS_ADAPTER.validate_python(raw)
                except Exception as exc:
                    log.warning("sec cache decode failed: %s", exc)
                    self._cache.delete(key)

        try:
            sections = self._primary.get_filing_sections(ticker, form_type=form_type)
        except SECError as exc:
            log.warning(
                "SECService: primary section fetch failed (%s); using fallback.", exc
            )
            sections = self._fallback.get_filing_sections(ticker, form_type=form_type)

        if self._cache is not None:
            self._cache.set_cached(key, _SECTIONS_ADAPTER.dump_python(sections, mode="json"))
        return sections


def _build_client(settings: Settings) -> SecEdgarClient | FallbackSECClient:
    if settings.sec_provider == "sec_edgar":
        return SecEdgarClient(
            user_agent=settings.sec_user_agent,
            timeout=settings.sec_timeout_seconds,
        )
    return FallbackSECClient()


def get_sec_service(
    settings: Settings | None = None,
    *,
    cache: CacheService | None = None,
) -> SECService:
    return SECService(settings or get_settings(), cache=cache)
