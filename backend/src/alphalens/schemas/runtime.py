"""Runtime and provider status schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from alphalens.schemas.common import APIModel

ProviderState = Literal[
    "real",
    "fallback",
    "connected",
    "disconnected",
    "memory_fallback",
]


class ProviderStatus(APIModel):
    name: str
    status: ProviderState
    reason: str | None = None


class RuntimeStatusResponse(APIModel):
    workspace_mode: Literal["demo", "live"] = "demo"
    providers: list[ProviderStatus] = Field(default_factory=list)
    data_sources: dict[str, str] = Field(default_factory=dict)
