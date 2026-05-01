"""High-level conversation memory facade."""

from __future__ import annotations

from typing import Any

from alphalens.core.config import Settings
from alphalens.memory.base import MemoryStore
from alphalens.memory.in_memory import InMemoryMemoryStore
from alphalens.memory.redis_memory import RedisMemoryStore


class MemoryService:
    """Facade around a ``MemoryStore`` with a simple message-oriented API."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        enabled: bool = True,
    ) -> None:
        self._store = store
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_history(self, conversation_id: str, *, user_id: str | None = None) -> dict[str, Any]:
        if not self._enabled:
            return {"messages": [], "metadata": []}
        key = _conversation_key(conversation_id, user_id=user_id)
        return self._store.get_conversation(key) or {
            "messages": [],
            "metadata": [],
        }

    def save_turn(
        self,
        conversation_id: str,
        *,
        user_id: str | None = None,
        user_message: dict[str, Any],
        assistant_message: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        if not self._enabled:
            return
        state = self.get_history(conversation_id, user_id=user_id)
        state.setdefault("messages", []).extend([user_message, assistant_message])
        state.setdefault("metadata", []).append(metadata)
        self._store.save_conversation(_conversation_key(conversation_id, user_id=user_id), state)

    def get_context_window(
        self,
        conversation_id: str,
        *,
        user_id: str | None = None,
        max_messages: int = 10,
    ) -> list[dict[str, Any]]:
        history = self.get_history(conversation_id, user_id=user_id)
        messages = history.get("messages", [])
        if not isinstance(messages, list):
            return []
        return list(messages[-max_messages:])

    def clear(self, conversation_id: str, *, user_id: str | None = None) -> None:
        if not self._enabled:
            return
        self._store.clear_conversation(_conversation_key(conversation_id, user_id=user_id))


def _conversation_key(conversation_id: str, *, user_id: str | None) -> str:
    if user_id is None:
        return conversation_id
    return f"{user_id}:{conversation_id}"


def build_memory_store(settings: Settings) -> MemoryStore:
    """Build the configured memory store, falling back safely as needed."""
    if settings.memory_backend == "redis" and settings.redis_url:
        return RedisMemoryStore(
            redis_url=settings.redis_url,
            ttl_seconds=settings.memory_ttl_seconds,
        )
    return InMemoryMemoryStore(ttl_seconds=settings.memory_ttl_seconds)


def get_memory_service(settings: Settings) -> MemoryService:
    return MemoryService(
        store=build_memory_store(settings),
        enabled=settings.memory_enabled,
    )
