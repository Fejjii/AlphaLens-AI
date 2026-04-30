"""FRED macro-data client.

Calls the St. Louis Fed FRED REST API to retrieve economic time-series
observations. All provider failures are surfaced as `MacroDataError` so
the service layer can fall back to the deterministic client cleanly.

FRED API reference:
    https://fred.stlouisfed.org/docs/api/fred/series_observations.html
"""

from __future__ import annotations

import logging
from datetime import date

import httpx

from alphalens.integrations.macro.base import MacroDataError
from alphalens.integrations.macro.fallback_client import (
    DEFAULT_SERIES,
    _SERIES_META,
)
from alphalens.schemas.macro import MacroObservation, MacroSeriesResponse, MacroSnapshot

log = logging.getLogger(__name__)

PROVIDER_NAME = "fred"
_FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# FRED uses "." to represent a missing / suppressed value.
_MISSING_VALUE = "."

# Series labels for display; falls back to the series_id if unknown.
_LABELS: dict[str, str] = {sid: meta["label"] for sid, meta in _SERIES_META.items()}
_UNITS: dict[str, str] = {sid: meta["unit"] for sid, meta in _SERIES_META.items()}


def _label(series_id: str) -> str:
    return _LABELS.get(series_id.upper(), series_id)


def _unit(series_id: str) -> str:
    return _UNITS.get(series_id.upper(), "")


class FredMacroClient:
    """Live FRED client backed by httpx (synchronous)."""

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        if not api_key:
            raise MacroDataError("FRED_API_KEY is required for FredMacroClient.")
        self._api_key = api_key
        self._timeout = timeout

    def get_series(self, series_id: str, limit: int = 5) -> MacroSeriesResponse:
        sid = series_id.upper()
        observations = self._fetch_observations(sid, limit=limit)
        return MacroSeriesResponse(
            series_id=sid,
            label=_label(sid),
            observations=observations,
            provider=PROVIDER_NAME,
        )

    def get_macro_snapshot(self) -> MacroSnapshot:
        observations: list[MacroObservation] = []
        for sid in DEFAULT_SERIES:
            try:
                obs = self._fetch_observations(sid, limit=1)
                observations.extend(obs)
            except MacroDataError as exc:
                # Partial failure: log and continue — a snapshot with some
                # missing series is still more useful than a total failure.
                log.warning("FRED snapshot: skipping %s — %s", sid, exc)

        if not observations:
            raise MacroDataError("FRED snapshot returned no observations for any series.")

        return MacroSnapshot(
            as_of=date.today(),
            observations=observations,
            provider=PROVIDER_NAME,
        )

    def _fetch_observations(self, series_id: str, limit: int) -> list[MacroObservation]:
        params = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": str(limit),
        }
        try:
            response = httpx.get(
                _FRED_BASE_URL,
                params=params,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise MacroDataError(
                f"FRED request timed out for series '{series_id}'."
            ) from exc
        except httpx.RequestError as exc:
            raise MacroDataError(
                f"FRED network error for series '{series_id}': {exc}"
            ) from exc

        if response.status_code == 429:
            raise MacroDataError(f"FRED rate limit exceeded for series '{series_id}'.")
        if response.status_code != 200:
            raise MacroDataError(
                f"FRED HTTP {response.status_code} for series '{series_id}'."
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise MacroDataError(
                f"FRED returned non-JSON payload for series '{series_id}'."
            ) from exc

        raw_obs = payload.get("observations")
        if not isinstance(raw_obs, list):
            raise MacroDataError(
                f"FRED payload missing 'observations' list for series '{series_id}'."
            )

        observations: list[MacroObservation] = []
        for entry in raw_obs:
            raw_value = entry.get("value", _MISSING_VALUE)
            if raw_value == _MISSING_VALUE:
                # FRED uses "." for suppressed / not-yet-released values; skip.
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                log.debug("FRED: skipping malformed value %r for %s", raw_value, series_id)
                continue

            raw_date = entry.get("date", "")
            try:
                obs_date = date.fromisoformat(raw_date)
            except (TypeError, ValueError):
                log.debug("FRED: skipping malformed date %r for %s", raw_date, series_id)
                continue

            observations.append(
                MacroObservation(
                    series_id=series_id,
                    label=_label(series_id),
                    value=value,
                    date=obs_date,
                    unit=_unit(series_id),
                    provider=PROVIDER_NAME,
                )
            )

        if not observations:
            raise MacroDataError(
                f"FRED returned no usable observations for series '{series_id}'."
            )

        return observations
