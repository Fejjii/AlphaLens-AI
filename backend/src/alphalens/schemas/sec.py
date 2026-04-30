"""Pydantic v2 schemas for SEC filing data."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class CompanyFiling(BaseModel):
    """Metadata for a single SEC filing."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    cik: str
    company_name: str
    form_type: str
    filing_date: date
    accession_number: str
    filing_url: str
    source: str
    provider: str


class FilingSection(BaseModel):
    """A text section extracted (or synthesized) from an SEC filing."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    form_type: str
    filing_date: date
    section: str
    text: str
    source: str
    provider: str


class FilingSearchResponse(BaseModel):
    """Result of searching for recent filings for a ticker."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    filings: list[CompanyFiling]
    provider: str
