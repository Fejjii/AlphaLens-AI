"""Schemas for conversation memory APIs."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from alphalens.schemas.common import APIModel


class MemoryMessage(APIModel):
    role: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMemory(APIModel):
    conversation_id: str
    messages: list[MemoryMessage] = Field(default_factory=list)
    metadata: list[dict[str, Any]] = Field(default_factory=list)


class MemoryClearResponse(APIModel):
    conversation_id: str
    cleared: bool = True
