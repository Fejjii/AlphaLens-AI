"""Conversation memory endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from alphalens.api.deps import CurrentUserDep, MemoryServiceDep
from alphalens.schemas.memory import ConversationMemory, MemoryClearResponse, MemoryMessage

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/{conversation_id}", response_model=ConversationMemory)
def get_memory(
    conversation_id: str,
    service: MemoryServiceDep,
    current_user: CurrentUserDep,
) -> ConversationMemory:
    history = service.get_history(conversation_id, user_id=current_user.id)
    messages = [
        MemoryMessage(
            role=str(message.get("role", "")),
            content=str(message.get("content", "")),
            metadata=dict(message.get("metadata", {})),
        )
        for message in history.get("messages", [])
    ]
    return ConversationMemory(
        conversation_id=conversation_id,
        messages=messages,
        metadata=list(history.get("metadata", [])),
    )


@router.delete("/{conversation_id}", response_model=MemoryClearResponse)
def clear_memory(
    conversation_id: str,
    service: MemoryServiceDep,
    current_user: CurrentUserDep,
) -> MemoryClearResponse:
    service.clear(conversation_id, user_id=current_user.id)
    return MemoryClearResponse(conversation_id=conversation_id)
