"""SQLAlchemy-backed conversation memory store."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.models import ConversationModel
from alphalens.memory.base import MemoryStore


class SqlAlchemyMemoryStore(MemoryStore):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = (
                session.query(ConversationModel)
                .filter(ConversationModel.conversation_id == conversation_id)
                .one_or_none()
            )
            if row is None:
                return None
            return {"messages": list(row.messages), "metadata": list(row.metadata_json)}

    def save_conversation(self, conversation_id: str, state: dict[str, Any]) -> None:
        now = datetime.now(tz=UTC)
        with self._session_factory() as session:
            row = (
                session.query(ConversationModel)
                .filter(ConversationModel.conversation_id == conversation_id)
                .one_or_none()
            )
            if row is None:
                row = ConversationModel(
                    user_id=state.get("user_id", "unknown"),
                    conversation_id=conversation_id,
                    messages=list(state.get("messages", [])),
                    metadata_json=list(state.get("metadata", [])),
                    updated_at=now,
                )
                session.add(row)
            else:
                row.messages = list(state.get("messages", []))
                row.metadata_json = list(state.get("metadata", []))
                row.updated_at = now
            session.commit()

    def append_message(self, conversation_id: str, message: dict[str, Any]) -> None:
        state = self.get_conversation(conversation_id) or {"messages": [], "metadata": []}
        state.setdefault("messages", []).append(message)
        self.save_conversation(conversation_id, state)

    def clear_conversation(self, conversation_id: str) -> None:
        with self._session_factory() as session:
            session.query(ConversationModel).filter(
                ConversationModel.conversation_id == conversation_id
            ).delete()
            session.commit()
