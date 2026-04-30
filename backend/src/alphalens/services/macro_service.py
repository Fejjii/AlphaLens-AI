"""Macro data service.

Selects the appropriate `MacroDataClient` based on configuration:
- If provider is 'fred' and a FRED API key is present: use FredMacroClient.
- Otherwise: use FallbackMacroClient.

If the FRED client is selected but fails at call time, the service
logs the error and transparently falls back to FallbackMacroClient
so the agent never errors due to provider unavailability.

Caching is optional and applied at the public method boundary (one entry
per series and one entry per snapshot).
"""

from __future__ import annotations

import logging

from alphalens.core.config import Settings, get_settings
from alphalens.integrations.macro.base import MacroDataError
from alphalens.integrations.macro.fallback_client import FallbackMacroClient
from alphalens.integrations.macro.fred_client import FredMacroClient
from alphalens.schemas.macro import MacroSeriesResponse, MacroSnapshot
from alphalens.services.cache_service import CacheService, build_cache_key

log = logging.getLogger(__name__)

_NAMESPACE = "macro"


class MacroService:
    """Provider-aware macro service with transparent fallback."""

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
        self._fallback = FallbackMacroClient()
        self._cache = cache

    def get_series(self, series_id: str, limit: int = 5) -> MacroSeriesResponse:
        key = build_cache_key(
            _NAMESPACE, {"op": "series", "id": series_id, "limit": limit}
        )
        cached = self._get_cached(key, MacroSeriesResponse)
        if cached is not None:
            return cached

        try:
            response = self._primary.get_series(series_id, limit=limit)
        except MacroDataError as exc:
            log.warning("MacroService: primary client failed (%s); using fallback.", exc)
            response = self._fallback.get_series(series_id, limit=limit)

        self._set_cached(key, response)
        return response

    def get_macro_snapshot(self) -> MacroSnapshot:
        key = build_cache_key(_NAMESPACE, {"op": "snapshot"})
        cached = self._get_cached(key, MacroSnapshot)
        if cached is not None:
            return cached

        try:
            snapshot = self._primary.get_macro_snapshot()
        except MacroDataError as exc:
            log.warning(
                "MacroService: primary snapshot failed (%s); using fallback.", exc
            )
            snapshot = self._fallback.get_macro_snapshot()

        self._set_cached(key, snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_cached(self, key, schema):
        if self._cache is None:
            return None
        raw = self._cache.get_cached(key)
        if raw is None:
            return None
        try:
            return schema.model_validate(raw)
        except Exception as exc:
            log.warning("macro cache decode failed: %s", exc)
            self._cache.delete(key)
            return None

    def _set_cached(self, key, value) -> None:
        if self._cache is None:
            return
        self._cache.set_cached(key, value.model_dump(mode="json"))


def _build_client(settings: Settings) -> FredMacroClient | FallbackMacroClient:
    """Return a live FRED client when fully configured; otherwise the fallback."""
    if settings.macro_data_provider == "fred" and settings.fred_api_key:
        return FredMacroClient(
            api_key=settings.fred_api_key,
            timeout=settings.macro_data_timeout_seconds,
        )
    return FallbackMacroClient()


def get_macro_service(
    settings: Settings | None = None,
    *,
    cache: CacheService | None = None,
) -> MacroService:
    return MacroService(settings or get_settings(), cache=cache)
