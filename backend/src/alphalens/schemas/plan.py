"""Plan configuration and usage schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from alphalens.schemas.common import APIModel

PlanName = Literal["free", "pro", "team"]


class PlanLimits(APIModel):
    monthly_chats: int | None = Field(default=None, ge=0)
    monthly_reports: int | None = Field(default=None, ge=0)
    monthly_scenarios: int | None = Field(default=None, ge=0)
    monthly_speech_uploads: int | None = Field(default=None, ge=0)
    monthly_estimated_cost_usd: float | None = Field(default=None, ge=0)


class PlanCapabilities(APIModel):
    tools: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)


class PlanResponse(APIModel):
    plan: PlanName
    limits: PlanLimits
    capabilities: PlanCapabilities
    description: str


class PlanUsage(APIModel):
    plan: PlanName
    monthly_usage: dict[str, int | float]
    remaining_quota: dict[str, int | float | None]
    limits: PlanLimits
    capabilities: PlanCapabilities
    current_month: str
