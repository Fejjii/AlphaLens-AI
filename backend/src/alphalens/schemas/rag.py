"""RAG-related response schemas."""

from __future__ import annotations

from pydantic import Field

from alphalens.schemas.common import APIModel


class RetrievedChunk(APIModel):
    source: str = Field(..., description="Document path relative to the KB root.")
    heading: str | None = None
    text: str
    score: float = Field(..., ge=0.0, le=1.0)
    chunk_id: str


class RagTestResponse(APIModel):
    query: str
    k: int
    chunks: list[RetrievedChunk]
