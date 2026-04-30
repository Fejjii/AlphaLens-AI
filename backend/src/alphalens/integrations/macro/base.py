"""Protocol and error type for macro-data clients."""

from __future__ import annotations

from typing import Protocol

from alphalens.schemas.macro import MacroSeriesResponse, MacroSnapshot


class MacroDataError(Exception):
    """Raised by a `MacroDataClient` for any provider-side failure.

    Covers: missing API key, HTTP errors, rate limits, timeouts,
    unexpected payloads, missing / malformed observations.
    The service layer catches this to fall back deterministically.
    """


class MacroDataClient(Protocol):
    """Minimal contract used by the macro service."""

    def get_series(self, series_id: str, limit: int = 5) -> MacroSeriesResponse:
        """Return recent observations for *series_id*.

        Raises `MacroDataError` on any provider-side failure.
        """
        ...

    def get_macro_snapshot(self) -> MacroSnapshot:
        """Return one latest observation for each default series.

        Raises `MacroDataError` on any provider-side failure.
        """
        ...
