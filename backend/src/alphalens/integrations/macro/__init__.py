"""Macro integration layer."""

from __future__ import annotations

from alphalens.integrations.macro.base import MacroDataClient, MacroDataError
from alphalens.integrations.macro.fallback_client import FallbackMacroClient
from alphalens.integrations.macro.fred_client import FredMacroClient

__all__ = [
    "MacroDataClient",
    "MacroDataError",
    "FallbackMacroClient",
    "FredMacroClient",
]
