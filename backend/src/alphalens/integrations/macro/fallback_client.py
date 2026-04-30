"""Deterministic offline macro-data client.

Returns hard-coded realistic observations for the four default series.
Values are intentionally stable so tests are reproducible and local
development works without any API key.
"""

from __future__ import annotations

from datetime import date

from alphalens.schemas.macro import MacroObservation, MacroSeriesResponse, MacroSnapshot

PROVIDER_NAME = "fallback"

_SERIES_META: dict[str, dict] = {
    "FEDFUNDS": {
        "label": "Federal Funds Effective Rate",
        "unit": "Percent",
        "observations": [
            {"date": date(2024, 11, 1), "value": 4.58},
            {"date": date(2024, 10, 1), "value": 4.83},
            {"date": date(2024, 9, 1), "value": 5.13},
            {"date": date(2024, 8, 1), "value": 5.33},
            {"date": date(2024, 7, 1), "value": 5.33},
        ],
    },
    "CPIAUCSL": {
        "label": "Consumer Price Index for All Urban Consumers",
        "unit": "Index 1982-1984=100",
        "observations": [
            {"date": date(2024, 11, 1), "value": 314.872},
            {"date": date(2024, 10, 1), "value": 315.664},
            {"date": date(2024, 9, 1), "value": 315.301},
            {"date": date(2024, 8, 1), "value": 314.796},
            {"date": date(2024, 7, 1), "value": 314.540},
        ],
    },
    "UNRATE": {
        "label": "Unemployment Rate",
        "unit": "Percent",
        "observations": [
            {"date": date(2024, 11, 1), "value": 4.2},
            {"date": date(2024, 10, 1), "value": 4.1},
            {"date": date(2024, 9, 1), "value": 4.1},
            {"date": date(2024, 8, 1), "value": 4.2},
            {"date": date(2024, 7, 1), "value": 4.3},
        ],
    },
    "GDP": {
        "label": "Gross Domestic Product",
        "unit": "Billions of Dollars",
        "observations": [
            {"date": date(2024, 7, 1), "value": 29365.0},
            {"date": date(2024, 4, 1), "value": 28888.9},
            {"date": date(2024, 1, 1), "value": 28516.4},
            {"date": date(2023, 10, 1), "value": 28026.5},
            {"date": date(2023, 7, 1), "value": 27622.1},
        ],
    },
}

DEFAULT_SERIES = ["FEDFUNDS", "CPIAUCSL", "UNRATE", "GDP"]


def _make_observations(series_id: str, meta: dict, limit: int) -> list[MacroObservation]:
    return [
        MacroObservation(
            series_id=series_id,
            label=meta["label"],
            value=obs["value"],
            date=obs["date"],
            unit=meta["unit"],
            provider=PROVIDER_NAME,
        )
        for obs in meta["observations"][:limit]
    ]


class FallbackMacroClient:
    """Hash-free deterministic client that never raises."""

    def get_series(self, series_id: str, limit: int = 5) -> MacroSeriesResponse:
        sid = series_id.upper()
        if sid not in _SERIES_META:
            # Return empty series rather than raising — deterministic fallback
            # should never blow up the agent.
            return MacroSeriesResponse(
                series_id=sid,
                label=sid,
                observations=[],
                provider=PROVIDER_NAME,
            )
        meta = _SERIES_META[sid]
        return MacroSeriesResponse(
            series_id=sid,
            label=meta["label"],
            observations=_make_observations(sid, meta, limit),
            provider=PROVIDER_NAME,
        )

    def get_macro_snapshot(self) -> MacroSnapshot:
        observations: list[MacroObservation] = []
        for sid in DEFAULT_SERIES:
            meta = _SERIES_META[sid]
            obs = _make_observations(sid, meta, 1)
            observations.extend(obs)

        return MacroSnapshot(
            as_of=date.today(),
            observations=observations,
            provider=PROVIDER_NAME,
        )
