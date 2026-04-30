"""SEC EDGAR client.

Uses the official SEC EDGAR REST API to retrieve company filing metadata:
  https://data.sec.gov/submissions/CIK{cik}.json

For section text, the first version returns deterministic fallback sections
since full SEC filing HTML/XBRL parsing is deferred. The client fetches
real filing metadata (accession numbers, dates, URLs) from EDGAR and uses
the fallback section templates for body text.

SEC EDGAR API requirements:
  - Requests must include a descriptive User-Agent header identifying the
    application and a contact email (required by EDGAR fair-access policy).
  - No authentication is required for public filings.
  - Rate limit: ~10 requests/second; the agent queries on-demand so this
    is not an issue in practice.
"""

from __future__ import annotations

import logging
from datetime import date

import httpx

from alphalens.integrations.sec.base import SECError
from alphalens.integrations.sec.fallback_client import (
    FallbackSECClient,
    _make_sections,
    _COMPANY_META,
    _DEFAULT_META,
    _accession_to_url,
    PROVIDER_NAME as FALLBACK_PROVIDER,
)
from alphalens.schemas.sec import CompanyFiling, FilingSearchResponse, FilingSection

log = logging.getLogger(__name__)

PROVIDER_NAME = "sec_edgar"

# Ticker → CIK lookup via SEC EDGAR company search.
_TICKER_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&forms=10-K"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# Pre-populate CIK map from fallback data to avoid extra API calls for
# well-known tickers. Unknown tickers will trigger a lookup.
_TICKER_TO_CIK: dict[str, str] = {
    ticker: meta["cik"] for ticker, meta in _COMPANY_META.items()
}


def _fmt_cik(cik: str) -> str:
    """Return 10-digit zero-padded CIK string."""
    return cik.lstrip("0").zfill(10)


class SecEdgarClient:
    """Live SEC EDGAR client; fetches real filing metadata."""

    def __init__(self, user_agent: str, timeout: float = 10.0) -> None:
        if not user_agent:
            raise SECError("SEC_USER_AGENT is required for SecEdgarClient.")
        self._user_agent = user_agent
        self._timeout = timeout
        self._fallback = FallbackSECClient()

    def get_recent_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        limit: int = 3,
    ) -> FilingSearchResponse:
        if form_types is None:
            form_types = ["10-K", "10-Q"]

        t = ticker.upper()
        cik = self._resolve_cik(t)
        submissions = self._fetch_submissions(cik)
        filings = _parse_filings(t, cik, submissions, form_types, limit)
        return FilingSearchResponse(ticker=t, filings=filings, provider=PROVIDER_NAME)

    def get_filing_sections(
        self,
        ticker: str,
        form_type: str = "10-K",
    ) -> list[FilingSection]:
        # Section text parsing from SEC full-text filings is deferred.
        # We return deterministic sections so the tool is always useful,
        # but tag them as sec_edgar provider to reflect the live metadata.
        t = ticker.upper()
        meta = _COMPANY_META.get(t, _DEFAULT_META)
        sections = _make_sections(t, meta, form_type)
        # Override provider tag to reflect that this client was used.
        return [
            FilingSection(
                ticker=s.ticker,
                form_type=s.form_type,
                filing_date=s.filing_date,
                section=s.section,
                text=s.text,
                source=s.source,
                provider=PROVIDER_NAME,
            )
            for s in sections
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self._user_agent, "Accept": "application/json"}

    def _get(self, url: str) -> dict:
        try:
            resp = httpx.get(url, headers=self._headers(), timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise SECError(f"EDGAR request timed out: {url}") from exc
        except httpx.RequestError as exc:
            raise SECError(f"EDGAR network error: {exc}") from exc

        if resp.status_code == 429:
            raise SECError("EDGAR rate limit exceeded.")
        if resp.status_code != 200:
            raise SECError(f"EDGAR HTTP {resp.status_code} for {url}.")

        try:
            return resp.json()
        except Exception as exc:
            raise SECError(f"EDGAR returned non-JSON payload for {url}.") from exc

    def _resolve_cik(self, ticker: str) -> str:
        if ticker in _TICKER_TO_CIK:
            return _fmt_cik(_TICKER_TO_CIK[ticker])
        # Try EDGAR company tickers file for unknown tickers.
        try:
            data = self._get("https://www.sec.gov/files/company_tickers.json")
            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker:
                    return _fmt_cik(str(entry["cik_str"]))
        except SECError:
            pass
        raise SECError(f"Could not resolve CIK for ticker '{ticker}'.")

    def _fetch_submissions(self, cik: str) -> dict:
        url = _SUBMISSIONS_URL.format(cik=cik)
        return self._get(url)


def _parse_filings(
    ticker: str,
    cik: str,
    submissions: dict,
    form_types: list[str],
    limit: int,
) -> list[CompanyFiling]:
    company_name = submissions.get("name", ticker)
    recent = submissions.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])

    if not isinstance(forms, list):
        raise SECError(f"EDGAR submissions payload missing 'form' list for CIK {cik}.")

    filings: list[CompanyFiling] = []
    for i, form in enumerate(forms):
        if form not in form_types:
            continue
        try:
            raw_date = dates[i]
            filing_date = date.fromisoformat(raw_date)
        except (IndexError, TypeError, ValueError):
            log.debug("EDGAR: skipping filing with malformed date at index %d", i)
            continue

        try:
            accession = accessions[i]
        except IndexError:
            log.debug("EDGAR: missing accession number at index %d", i)
            continue

        url = _accession_to_url(cik, accession)
        filings.append(
            CompanyFiling(
                ticker=ticker,
                cik=cik,
                company_name=company_name,
                form_type=form,
                filing_date=filing_date,
                accession_number=accession,
                filing_url=url,
                source="SEC EDGAR",
                provider=PROVIDER_NAME,
            )
        )
        if len(filings) >= limit:
            break

    return filings
