"""Schemas for user-scoped conversation APIs."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from alphalens.schemas.common import APIModel
from alphalens.schemas.memory import MemoryMessage


class ConversationCreateRequest(APIModel):
    title: str | None = Field(default=None, max_length=120)


class ConversationCreateResponse(APIModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationSummary(APIModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationDetail(APIModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[MemoryMessage] = Field(default_factory=list)
    metadata: list[dict[str, Any]] = Field(default_factory=list)
