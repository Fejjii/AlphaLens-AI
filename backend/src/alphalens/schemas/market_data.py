"""Schemas for market-data integrations.

`MarketQuote` is the normalized cross-provider quote shape the agent and
tooling consume. Each provider client is responsible for translating its
native payload into this model so downstream code stays provider-agnostic.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from alphalens.schemas.common import APIModel


class MarketQuote(APIModel):
    """A single point-in-time equity quote."""

    ticker: str = Field(..., min_length=1, max_length=12)
    price: Decimal = Field(..., ge=0)
    previous_close: Decimal = Field(..., ge=0)
    change: Decimal
    change_percent: float
    currency: str = Field(default="USD", min_length=3, max_length=3)
    as_of: datetime
    provider: str = Field(..., min_length=1, max_length=64)
