"""Thread-safe in-memory conversation store with TTL."""

from __future__ import annotations

import copy
import time
from threading import Lock
from typing import Any

from alphalens.memory.base import MemoryStore


class InMemoryMemoryStore(MemoryStore):
    """Process-local conversation memory with per-conversation TTL."""

    def __init__(self, *, ttl_seconds: int = 3600) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[dict[str, Any], float]] = {}
        self._lock = Lock()

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._store.get(conversation_id)
            if entry is None:
                return None
            state, expires_at = entry
            if time.monotonic() >= expires_at:
                self._store.pop(conversation_id, None)
                return None
            return copy.deepcopy(state)

    def save_conversation(self, conversation_id: str, state: dict[str, Any]) -> None:
        with self._lock:
            self._store[conversation_id] = (copy.deepcopy(state), self._expires_at())

    def append_message(self, conversation_id: str, message: dict[str, Any]) -> None:
        with self._lock:
            state, _ = self._store.get(
                conversation_id,
                ({"messages": [], "metadata": []}, self._expires_at()),
            )
            state = copy.deepcopy(state)
            state.setdefault("messages", []).append(copy.deepcopy(message))
            self._store[conversation_id] = (state, self._expires_at())

    def clear_conversation(self, conversation_id: str) -> None:
        with self._lock:
            self._store.pop(conversation_id, None)

    def _expires_at(self) -> float:
        return time.monotonic() + self._ttl_seconds
