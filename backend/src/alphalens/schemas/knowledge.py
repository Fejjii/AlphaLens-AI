"""Knowledge base API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from alphalens.schemas.common import APIModel


class KnowledgeDocument(APIModel):
    document_id: str
    document_title: str
    source: str
    file_type: str
    chunk_count: int = Field(default=0, ge=0)
    indexed_at: datetime
    collection: str
    status: str = "indexed"


class KnowledgeStatsResponse(APIModel):
    document_count: int = Field(default=0, ge=0)
    chunk_count: int = Field(default=0, ge=0)
    collection: str
    vector_mode: str
    seeded_documents: int = Field(default=0, ge=0)
    uploaded_documents: int = Field(default=0, ge=0)
    seeded_source_titles: list[str] = Field(default_factory=list)
    uploaded_source_titles: list[str] = Field(default_factory=list)


class KnowledgeUploadResponse(APIModel):
    document: KnowledgeDocument
    accepted_file_types: list[str]
    max_file_size_bytes: int


class KnowledgeSearchResult(APIModel):
    document_id: str
    document_title: str
    chunk_id: str
    source: str
    score: float = Field(ge=0.0, le=1.0)
    snippet: str
    section: str | None = None


class KnowledgeSearchRequest(APIModel):
    query: str = Field(..., min_length=1)
    k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResponse(APIModel):
    query: str
    k: int
    results: list[KnowledgeSearchResult] = Field(default_factory=list)
    retrieval_mode: str
