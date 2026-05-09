"""Recursively convert values to JSON-serializable structures for persistence layers."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any


def to_json_safe(value: Any, *, _depth: int = 0) -> Any:
    """Convert Pydantic-heavy / mixed Python objects into JSON-friendly data.

    - ``None``, scalars: unchanged
    - ``datetime`` / ``date``: ISO-8601 string
    - ``Enum``: ``.value``
    - ``dict`` / ``list`` / ``tuple`` / ``set``: recurse
    - Pydantic v2 models: ``model_dump(mode="python")`` then recurse
    - Other objects: ``str()`` fallback (never raises for serialization)
    """
    if _depth > 48:
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            dumped = value.model_dump(mode="python")
        except Exception:
            dumped = str(value)
        return to_json_safe(dumped, _depth=_depth + 1)
    if isinstance(value, dict):
        return {str(k): to_json_safe(v, _depth=_depth + 1) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_json_safe(item, _depth=_depth + 1) for item in value]
    try:
        return str(value)
    except Exception:
        return "<unserializable>"
