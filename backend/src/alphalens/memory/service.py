"""High-level conversation memory facade."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from alphalens.core.config import Settings
from alphalens.memory.base import MemoryStore
from alphalens.memory.in_memory import InMemoryMemoryStore
from alphalens.memory.redis_memory import RedisMemoryStore

_TITLE_MAX_LEN = 60


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
        now = datetime.now(tz=UTC).isoformat()
        state.setdefault("created_at", now)
        state["updated_at"] = now
        state.setdefault("messages", []).extend([user_message, assistant_message])
        state.setdefault("metadata", []).append(metadata)
        if user_id is not None:
            state["user_id"] = user_id
        for message in state.get("messages", []):
            if not isinstance(message, dict):
                continue
            if message.get("role") != "user":
                continue
            first_user = str(message.get("content", "")).strip()
            if first_user:
                state["title"] = first_user[:_TITLE_MAX_LEN]
                break
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

    def create_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str,
        title: str | None = None,
    ) -> None:
        if not self._enabled:
            return
        now = datetime.now(tz=UTC).isoformat()
        self._store.save_conversation(
            _conversation_key(conversation_id, user_id=user_id),
            {
                "user_id": user_id,
                "messages": [],
                "metadata": [],
                "title": title,
                "created_at": now,
                "updated_at": now,
            },
        )

    def list_conversations(self, *, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        if not self._enabled:
            return []
        fetch_limit = max(limit * 4, limit + 10)
        rows = self._store.list_conversations(user_id=user_id, limit=fetch_limit)
        built: list[dict[str, Any]] = []
        for row in rows:
            key = str(row.get("conversation_id", ""))
            state = row.get("state", {})
            if not isinstance(state, dict):
                continue
            conversation_id = key.split(":", 1)[1] if ":" in key else key
            messages = state.get("messages", [])
            if not isinstance(messages, list):
                messages = []
            message_count = len(messages)
            if message_count == 0:
                continue
            title = self._conversation_title(messages=messages, explicit_title=state.get("title"))
            built.append(
                {
                    "conversation_id": conversation_id,
                    "title": title,
                    "created_at": str(state.get("created_at") or state.get("updated_at") or ""),
                    "updated_at": str(state.get("updated_at") or state.get("created_at") or ""),
                    "message_count": message_count,
                }
            )
        deduped: dict[str, dict[str, Any]] = {}
        for item in built:
            cid = str(item["conversation_id"])
            prev = deduped.get(cid)
            if prev is None or str(item.get("updated_at", "")) > str(prev.get("updated_at", "")):
                deduped[cid] = item
        result = sorted(
            deduped.values(),
            key=lambda item: str(item.get("updated_at", "")),
            reverse=True,
        )
        return result[:limit]

    @staticmethod
    def _conversation_title(*, messages: list[Any], explicit_title: Any) -> str:
        if isinstance(explicit_title, str) and explicit_title.strip():
            return explicit_title.strip()[:_TITLE_MAX_LEN]
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") != "user":
                continue
            content = str(message.get("content") or "").strip()
            if content:
                return content[:_TITLE_MAX_LEN]
        return "Untitled chat"


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
