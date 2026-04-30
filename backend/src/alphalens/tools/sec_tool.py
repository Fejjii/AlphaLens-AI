"""SEC filings tool.

Wraps `SECService` to surface filing metadata and key text sections.

Tool contract:
    input:  ticker: str
            form_type: str (default "10-K")
    output: ToolResult.data = {
        "provider": "fallback" | "sec_edgar",
        "ticker": "NVDA",
        "filings": [
            {
                "form_type": "10-K",
                "filing_date": "2024-01-26",
                "accession_number": "...",
                "filing_url": "https://...",
                "company_name": "...",
                "provider": "...",
            },
            ...
        ],
        "sections": [
            {
                "section": "Risk Factors",
                "text": "...",
                "filing_date": "2024-01-26",
                "form_type": "10-K",
                "provider": "...",
            },
            ...
        ],
    }
"""

from __future__ import annotations

from alphalens.schemas.sec import CompanyFiling, FilingSection
from alphalens.services.sec_service import SECService
from alphalens.tools.registry import Tool, ToolResult


def make_sec_filings_tool(service: SECService) -> Tool:
    def _run(ticker: str, form_type: str = "10-K") -> ToolResult:
        t = ticker.upper()
        filing_resp = service.get_recent_filings(t, form_types=[form_type], limit=3)
        sections = service.get_filing_sections(t, form_type=form_type)

        providers = {filing_resp.provider, *(s.provider for s in sections)}
        provider = providers.pop() if len(providers) == 1 else "mixed"

        summary = _build_summary(t, form_type, filing_resp.filings, sections)
        return ToolResult(
            name="sec_filings",
            summary=summary,
            data={
                "provider": provider,
                "ticker": t,
                "filings": [_filing_to_dict(f) for f in filing_resp.filings],
                "sections": [_section_to_dict(s) for s in sections],
            },
        )

    return Tool(
        name="sec_filings",
        description=(
            "Return recent SEC filing metadata and key text sections "
            "(Business Overview, Risk Factors, Management Discussion, "
            "AI/Technology Exposure) for a given ticker."
        ),
        func=_run,
        parameters={
            "ticker": "Ticker symbol (e.g. NVDA)",
            "form_type": "SEC form type, default '10-K'",
        },
    )


def _filing_to_dict(f: CompanyFiling) -> dict:
    return {
        "form_type": f.form_type,
        "filing_date": f.filing_date.isoformat(),
        "accession_number": f.accession_number,
        "filing_url": f.filing_url,
        "company_name": f.company_name,
        "provider": f.provider,
    }


def _section_to_dict(s: FilingSection) -> dict:
    return {
        "section": s.section,
        "text": s.text,
        "filing_date": s.filing_date.isoformat(),
        "form_type": s.form_type,
        "provider": s.provider,
    }


def _build_summary(
    ticker: str,
    form_type: str,
    filings: list[CompanyFiling],
    sections: list[FilingSection],
) -> str:
    if not filings and not sections:
        return f"No SEC filing data available for {ticker}."
    filing_dates = [f.filing_date.isoformat() for f in filings]
    section_names = [s.section for s in sections]
    return (
        f"{ticker} {form_type} filings: {', '.join(filing_dates) or 'none'}. "
        f"Sections: {', '.join(section_names) or 'none'}."
    )
