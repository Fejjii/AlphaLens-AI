"""Conversation lifecycle endpoints for Agent Chat UI."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status

from alphalens.api.deps import CurrentUserDep, MemoryServiceDep
from alphalens.schemas.conversations import (
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationDetail,
    ConversationSummary,
)
from alphalens.schemas.memory import MemoryMessage

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationCreateResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreateRequest,
    service: MemoryServiceDep,
    current_user: CurrentUserDep,
) -> ConversationCreateResponse:
    conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
    now = datetime.now(tz=UTC).isoformat()
    title = (payload.title or "").strip() or "New chat"
    service.create_conversation(conversation_id, user_id=current_user.id, title=title)
    return ConversationCreateResponse(
        conversation_id=conversation_id,
        title=title,
        created_at=now,
        updated_at=now,
        message_count=0,
    )


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    service: MemoryServiceDep,
    current_user: CurrentUserDep,
    limit: int = Query(default=6, ge=1, le=100),
) -> list[ConversationSummary]:
    rows = service.list_conversations(user_id=current_user.id, limit=limit)
    return [ConversationSummary(**row) for row in rows]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    service: MemoryServiceDep,
    current_user: CurrentUserDep,
) -> ConversationDetail:
    history = service.get_history(conversation_id, user_id=current_user.id)
    messages = [
        MemoryMessage(
            role=str(message.get("role", "")),
            content=str(message.get("content", "")),
            metadata=dict(message.get("metadata", {})),
        )
        for message in history.get("messages", [])
    ]
    if not messages and not history.get("metadata"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    title = str(history.get("title") or "").strip()
    if not title:
        first_user = next(
            (m.content for m in messages if m.role == "user" and m.content.strip()),
            "Untitled chat",
        )
        title = first_user[:60]
    return ConversationDetail(
        conversation_id=conversation_id,
        title=title,
        created_at=str(history.get("created_at") or history.get("updated_at") or ""),
        updated_at=str(history.get("updated_at") or history.get("created_at") or ""),
        messages=messages,
        metadata=list(history.get("metadata", [])),
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    service: MemoryServiceDep,
    current_user: CurrentUserDep,
) -> None:
    service.clear(conversation_id, user_id=current_user.id)
