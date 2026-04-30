"""Macro-snapshot tool.

Wraps `MacroService` to expose macroeconomic context to the agent.

Tool contract:
    input:  series_ids: list[str] | None
            Pass an explicit list to request specific series, or omit
            (None / empty) to receive the default snapshot
            (FEDFUNDS, CPIAUCSL, UNRATE, GDP).
    output: ToolResult.data = {
        "provider": "fallback" | "fred",
        "as_of": "<iso8601 date>",
        "observations": [
            {
                "series_id": "FEDFUNDS",
                "label": "Federal Funds Effective Rate",
                "value": 4.58,
                "date": "2024-11-01",
                "unit": "Percent",
                "provider": "...",
            },
            ...
        ],
    }
"""

from __future__ import annotations

from alphalens.schemas.macro import MacroObservation
from alphalens.services.macro_service import MacroService
from alphalens.tools.registry import Tool, ToolResult


def make_macro_snapshot_tool(service: MacroService) -> Tool:
    def _run(series_ids: list[str] | None = None) -> ToolResult:
        if series_ids:
            observations: list[MacroObservation] = []
            provider_set: set[str] = set()
            for sid in series_ids:
                resp = service.get_series(sid, limit=1)
                observations.extend(resp.observations)
                provider_set.add(resp.provider)
            provider = provider_set.pop() if len(provider_set) == 1 else "mixed"
            from datetime import date

            as_of = date.today()
        else:
            snapshot = service.get_macro_snapshot()
            observations = list(snapshot.observations)
            provider = snapshot.provider
            as_of = snapshot.as_of

        summary = _build_summary(observations)
        return ToolResult(
            name="macro_snapshot",
            summary=summary,
            data={
                "provider": provider,
                "as_of": as_of.isoformat(),
                "observations": [_obs_to_dict(o) for o in observations],
            },
        )

    return Tool(
        name="macro_snapshot",
        description=(
            "Return the latest macro-economic indicators "
            "(Fed Funds rate, CPI, unemployment, GDP). "
            "Pass series_ids to request specific FRED series."
        ),
        func=_run,
        parameters={"series_ids": "Optional list of FRED series IDs"},
    )


def _obs_to_dict(obs: MacroObservation) -> dict:
    return {
        "series_id": obs.series_id,
        "label": obs.label,
        "value": obs.value,
        "date": obs.date.isoformat(),
        "unit": obs.unit,
        "provider": obs.provider,
    }


def _build_summary(observations: list[MacroObservation]) -> str:
    if not observations:
        return "No macro observations available."
    parts = [f"{o.series_id}={o.value} {o.unit} ({o.date})" for o in observations]
    return "Macro snapshot: " + "; ".join(parts)
