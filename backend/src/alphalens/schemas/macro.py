"""Pydantic v2 schemas for macro-economic data.

These are shared across the integration, service, and tool layers.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MacroObservation(BaseModel):
    """A single data point from a macro time-series."""

    model_config = ConfigDict(frozen=True)

    series_id: str
    label: str
    value: float
    date: date
    unit: str
    provider: str


class MacroSeriesResponse(BaseModel):
    """Full time-series for one FRED series."""

    model_config = ConfigDict(frozen=True)

    series_id: str
    label: str
    observations: list[MacroObservation]
    provider: str


class MacroSnapshot(BaseModel):
    """Aggregated macro context at a point in time (one obs per series)."""

    model_config = ConfigDict(frozen=True)

    as_of: date
    observations: list[MacroObservation] = Field(default_factory=list)
    provider: str
