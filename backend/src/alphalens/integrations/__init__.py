"""External integrations (market data, brokers, custodians, news).

Defined as Protocols so concrete adapters can be swapped per-environment
(live, sandbox, fake) without touching service-layer code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    price: Decimal
    as_of: datetime


class MarketDataClient(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...


class BrokerClient(Protocol):
    def submit_order(self, *, symbol: str, quantity: Decimal, side: str) -> str: ...
