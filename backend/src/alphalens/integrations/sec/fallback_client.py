"""Deterministic offline SEC client.

Returns hard-coded realistic filing sections for a set of well-known
tickers. Values are stable so tests are reproducible and the agent is
functional without any external API access.
"""

from __future__ import annotations

from datetime import date

from alphalens.schemas.sec import CompanyFiling, FilingSearchResponse, FilingSection

PROVIDER_NAME = "fallback"

# CIK numbers are real (used in fallback filing URL construction).
_COMPANY_META: dict[str, dict] = {
    "NVDA": {
        "cik": "0001045810",
        "company_name": "NVIDIA Corp",
        "latest_10k": date(2024, 1, 26),
        "latest_10q": date(2024, 8, 28),
        "accession_10k": "0001045810-24-000009",
        "accession_10q": "0001045810-24-000040",
    },
    "MSFT": {
        "cik": "0000789019",
        "company_name": "Microsoft Corp",
        "latest_10k": date(2024, 7, 30),
        "latest_10q": date(2024, 10, 30),
        "accession_10k": "0000789019-24-000082",
        "accession_10q": "0000789019-24-000113",
    },
    "AAPL": {
        "cik": "0000320193",
        "company_name": "Apple Inc",
        "latest_10k": date(2024, 11, 1),
        "latest_10q": date(2024, 8, 2),
        "accession_10k": "0000320193-24-000123",
        "accession_10q": "0000320193-24-000085",
    },
    "TSM": {
        "cik": "0001046179",
        "company_name": "Taiwan Semiconductor Manufacturing Co Ltd",
        "latest_10k": date(2024, 4, 22),
        "latest_10q": date(2024, 10, 18),
        "accession_10k": "0001046179-24-000010",
        "accession_10q": "0001046179-24-000022",
    },
    "AMD": {
        "cik": "0000002488",
        "company_name": "Advanced Micro Devices Inc",
        "latest_10k": date(2024, 2, 26),
        "latest_10q": date(2024, 10, 29),
        "accession_10k": "0000002488-24-000012",
        "accession_10q": "0000002488-24-000056",
    },
}

_DEFAULT_META: dict = {
    "cik": "0000000000",
    "company_name": "Unknown Company",
    "latest_10k": date(2024, 3, 1),
    "latest_10q": date(2024, 9, 1),
    "accession_10k": "0000000000-24-000001",
    "accession_10q": "0000000000-24-000002",
}

# Realistic section text templates.  {ticker} and {company} are substituted.
_SECTION_TEMPLATES: dict[str, str] = {
    "Business Overview": (
        "{company} ({ticker}) operates at the intersection of advanced semiconductor "
        "design, software, and systems integration. The company designs and sells "
        "graphics processing units (GPUs), system-on-chip units (SoCs), and related "
        "software for gaming, professional visualisation, data-centre AI acceleration, "
        "and automotive applications. {ticker}'s CUDA platform has become the de-facto "
        "standard for general-purpose GPU computing, creating a durable competitive moat "
        "in AI training and inference workloads."
    ),
    "Risk Factors": (
        "Demand for {ticker}'s products may be adversely affected by macroeconomic "
        "conditions including interest rate increases, inflation, tightening credit "
        "markets, and geopolitical instability. Export-control regulations, particularly "
        "U.S. restrictions on high-performance chips shipped to China and other "
        "restricted jurisdictions, could materially reduce addressable market size. "
        "Supply concentration in Taiwan introduces geopolitical and natural-disaster risk "
        "in the semiconductor supply chain. Customer concentration in hyperscaler cloud "
        "providers (Microsoft, Google, Amazon, Meta) means revenue is sensitive to "
        "capital-expenditure cycles in the cloud industry. Rapid technological change "
        "could erode {ticker}'s architectural advantages if competitors close the gap "
        "in GPU performance-per-watt or software ecosystem depth."
    ),
    "Management Discussion": (
        "Revenue for the fiscal year ended January 2024 was $60.9 billion, up 122% "
        "year over year, driven primarily by Data Center segment growth of 217%. "
        "Gross margin expanded to 72.7% reflecting favorable product mix toward "
        "higher-ASP data-centre SKUs. Management expects continued strong demand for "
        "AI infrastructure and highlighted the ramp of H200 and upcoming Blackwell "
        "architecture as key growth drivers. Operating expenses grew 23% year-over-year "
        "as {ticker} increased investment in R&D and go-to-market capabilities for "
        "enterprise AI software."
    ),
    "AI / Technology Exposure": (
        "{ticker} is one of the primary beneficiaries of the AI infrastructure build-out. "
        "The Data Center segment — encompassing A100, H100, H200, and Blackwell GPUs — "
        "accounts for over 80% of revenue and is growing at triple-digit rates. "
        "{ticker}'s software ecosystem (CUDA, cuDNN, TensorRT, NeMo, Triton Inference "
        "Server) creates switching costs that make it difficult for customers to migrate "
        "to alternative GPU architectures. The company is expanding into AI software "
        "subscriptions, networking (InfiniBand and Spectrum-X Ethernet), and sovereign AI "
        "infrastructure deals, diversifying revenue streams beyond chip sales."
    ),
}


def _accession_to_url(cik: str, accession: str) -> str:
    clean = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{clean}/{accession}-index.htm"


def _make_filing(ticker: str, meta: dict, form_type: str) -> CompanyFiling:
    if form_type == "10-K":
        filing_date = meta["latest_10k"]
        accession = meta["accession_10k"]
    else:
        filing_date = meta["latest_10q"]
        accession = meta["accession_10q"]

    return CompanyFiling(
        ticker=ticker,
        cik=meta["cik"],
        company_name=meta["company_name"],
        form_type=form_type,
        filing_date=filing_date,
        accession_number=accession,
        filing_url=_accession_to_url(meta["cik"], accession),
        source="SEC EDGAR (fallback)",
        provider=PROVIDER_NAME,
    )


def _make_sections(ticker: str, meta: dict, form_type: str) -> list[FilingSection]:
    company = meta["company_name"]
    filing_date = meta["latest_10k"] if form_type == "10-K" else meta["latest_10q"]
    accession = meta["accession_10k"] if form_type == "10-K" else meta["accession_10q"]
    source = _accession_to_url(meta["cik"], accession)

    return [
        FilingSection(
            ticker=ticker,
            form_type=form_type,
            filing_date=filing_date,
            section=section_name,
            text=template.format(ticker=ticker, company=company),
            source=source,
            provider=PROVIDER_NAME,
        )
        for section_name, template in _SECTION_TEMPLATES.items()
    ]


class FallbackSECClient:
    """Deterministic SEC client that never raises."""

    def get_recent_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        limit: int = 3,
    ) -> FilingSearchResponse:
        if form_types is None:
            form_types = ["10-K", "10-Q"]
        t = ticker.upper()
        meta = _COMPANY_META.get(t, _DEFAULT_META)
        filings = [
            _make_filing(t, meta, ft)
            for ft in form_types
            for _ in range(1)  # one filing per type in fallback
        ][:limit]
        return FilingSearchResponse(ticker=t, filings=filings, provider=PROVIDER_NAME)

    def get_filing_sections(
        self,
        ticker: str,
        form_type: str = "10-K",
    ) -> list[FilingSection]:
        t = ticker.upper()
        meta = _COMPANY_META.get(t, _DEFAULT_META)
        return _make_sections(t, meta, form_type)
