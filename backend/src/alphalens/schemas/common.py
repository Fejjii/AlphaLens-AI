"""Shared schema primitives used across endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base model with strict, immutable defaults for response/request schemas."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class Money(APIModel):
    amount: Decimal = Field(..., description="Amount in the smallest unit-aware decimal.")
    currency: str = Field(default="USD", min_length=3, max_length=3)


class HealthStatus(APIModel):
    status: str = Field(default="ok")
    version: str
    environment: str


class ErrorResponse(APIModel):
    code: str
    message: str
    details: Any | None = None
    request_id: str | None = None
