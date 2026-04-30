"""RAG inspection endpoints.

These are intentionally exposed for development and evaluation. They
will be locked behind auth before production rollout.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from alphalens.api.deps import RAGServiceDep
from alphalens.schemas.rag import RagTestResponse, RetrievedChunk

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/test", response_model=RagTestResponse)
def rag_test(
    service: RAGServiceDep,
    query: str = Query(..., min_length=1, description="Free-text query."),
    k: int = Query(5, ge=1, le=20),
) -> RagTestResponse:
    chunks = service.get_relevant_context(query, k=k)
    return RagTestResponse(
        query=query,
        k=k,
        chunks=[
            RetrievedChunk(
                source=c.source,
                heading=c.heading,
                text=c.text,
                score=c.score,
                chunk_id=c.chunk_id,
            )
            for c in chunks
        ],
    )
