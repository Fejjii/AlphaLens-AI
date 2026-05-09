"""Conversation memory store protocol."""

from __future__ import annotations

from typing import Any, Protocol


class MemoryStore(Protocol):
    """Minimal storage contract for conversation memory."""

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None: ...

    def save_conversation(self, conversation_id: str, state: dict[str, Any]) -> None: ...

    def append_message(self, conversation_id: str, message: dict[str, Any]) -> None: ...

    def clear_conversation(self, conversation_id: str) -> None: ...

    def list_conversations(self, *, user_id: str, limit: int = 20) -> list[dict[str, Any]]: ...
