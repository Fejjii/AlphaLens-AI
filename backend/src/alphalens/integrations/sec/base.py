"""Protocol and error type for SEC data clients."""

from __future__ import annotations

from typing import Protocol

from alphalens.schemas.sec import FilingSearchResponse, FilingSection


class SECError(Exception):
    """Raised by a `SECClient` on any provider-side failure.

    Covers: HTTP errors, timeouts, malformed payloads, rate limits,
    unknown tickers, missing CIK mappings.
    The service layer catches this to fall back to the deterministic client.
    """


class SECClient(Protocol):
    """Minimal contract used by the SEC service."""

    def get_recent_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        limit: int = 3,
    ) -> FilingSearchResponse:
        """Return recent filing metadata for *ticker*.

        Raises `SECError` on any provider-side failure.
        """
        ...

    def get_filing_sections(
        self,
        ticker: str,
        form_type: str = "10-K",
    ) -> list[FilingSection]:
        """Return key text sections for the most recent *form_type* filing.

        Raises `SECError` on any provider-side failure.
        """
        ...
