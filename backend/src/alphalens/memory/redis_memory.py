"""Redis-backed conversation memory with safe in-memory fallback."""

from __future__ import annotations

import json
from typing import Any

from alphalens.core.logging import get_logger
from alphalens.memory.base import MemoryStore
from alphalens.memory.in_memory import InMemoryMemoryStore

logger = get_logger(__name__)


class RedisMemoryStore(MemoryStore):
    """Redis-backed memory store that never raises to callers.

    When Redis cannot be initialized or any Redis operation fails, the store
    degrades to an internal in-memory fallback so conversation memory remains
    available for the running process.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        ttl_seconds: int,
        client: Any | None = None,
        fallback: InMemoryMemoryStore | None = None,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._fallback = fallback or InMemoryMemoryStore(ttl_seconds=ttl_seconds)
        if client is not None:
            self._client = client
            return
        try:
            import redis

            self._client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._client.ping()
        except Exception as exc:
            logger.warning("redis_memory_init_failed", error=str(exc))
            self._client = None

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        if self._client is None:
            return self._fallback.get_conversation(conversation_id)
        try:
            raw = self._client.get(self._key(conversation_id))
        except Exception as exc:
            logger.warning(
                "redis_memory_get_failed",
                conversation_id=conversation_id,
                error=str(exc),
            )
            return self._fallback.get_conversation(conversation_id)
        if raw is None:
            return self._fallback.get_conversation(conversation_id)
        try:
            return json.loads(raw)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "redis_memory_decode_failed",
                conversation_id=conversation_id,
                error=str(exc),
            )
            return self._fallback.get_conversation(conversation_id)

    def save_conversation(self, conversation_id: str, state: dict[str, Any]) -> None:
        self._fallback.save_conversation(conversation_id, state)
        if self._client is None:
            return
        try:
            self._client.set(
                self._key(conversation_id),
                json.dumps(state, default=str),
                ex=self._ttl_seconds,
            )
        except Exception as exc:
            logger.warning(
                "redis_memory_set_failed",
                conversation_id=conversation_id,
                error=str(exc),
            )

    def append_message(self, conversation_id: str, message: dict[str, Any]) -> None:
        state = self.get_conversation(conversation_id) or {"messages": [], "metadata": []}
        state.setdefault("messages", []).append(message)
        self.save_conversation(conversation_id, state)

    def clear_conversation(self, conversation_id: str) -> None:
        self._fallback.clear_conversation(conversation_id)
        if self._client is None:
            return
        try:
            self._client.delete(self._key(conversation_id))
        except Exception as exc:
            logger.warning(
                "redis_memory_delete_failed",
                conversation_id=conversation_id,
                error=str(exc),
            )

    def list_conversations(self, *, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._fallback.list_conversations(user_id=user_id, limit=limit)
        if self._client is None:
            return rows
        try:
            pattern = self._key(f"{user_id}:*")
            for redis_key in self._client.scan_iter(match=pattern, count=100):
                key_str = (
                    redis_key.decode("utf-8", errors="replace")
                    if isinstance(redis_key, (bytes, bytearray))
                    else str(redis_key)
                )
                raw = self._client.get(redis_key)
                if raw is None:
                    continue
                try:
                    state = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if not isinstance(state, dict):
                    continue
                prefix = "alphalens:memory:"
                conversation_id = key_str[len(prefix) :] if key_str.startswith(prefix) else key_str
                rows.append({"conversation_id": conversation_id, "state": state})
        except Exception as exc:
            logger.warning("redis_memory_list_failed", user_id=user_id, error=str(exc))
        deduped: dict[str, dict[str, Any]] = {}
        for row in rows:
            deduped[str(row["conversation_id"])] = row
        merged = list(deduped.values())
        merged.sort(
            key=lambda item: str(item["state"].get("updated_at") or ""),
            reverse=True,
        )
        return merged[:limit]

    def _key(self, conversation_id: str) -> str:
        return f"alphalens:memory:{conversation_id}"
