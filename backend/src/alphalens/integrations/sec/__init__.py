"""SEC integration layer."""

from __future__ import annotations

from alphalens.integrations.sec.base import SECClient, SECError
from alphalens.integrations.sec.fallback_client import FallbackSECClient
from alphalens.integrations.sec.sec_edgar_client import SecEdgarClient

__all__ = [
    "SECClient",
    "SECError",
    "FallbackSECClient",
    "SecEdgarClient",
]
