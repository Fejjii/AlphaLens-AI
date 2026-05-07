"""Knowledge base ingestion and retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from alphalens.api.deps import RAGServiceDep
from alphalens.schemas.knowledge import (
    KnowledgeDocument,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
    KnowledgeUploadResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/stats", response_model=KnowledgeStatsResponse)
def knowledge_stats(
    rag: RAGServiceDep,
) -> KnowledgeStatsResponse:
    return rag.get_stats()


@router.get("/documents", response_model=list[KnowledgeDocument])
def knowledge_documents(
    rag: RAGServiceDep,
) -> list[KnowledgeDocument]:
    return rag.list_documents()


@router.post("/upload", response_model=KnowledgeUploadResponse)
async def knowledge_upload(
    rag: RAGServiceDep,
    file: UploadFile = File(...),
) -> KnowledgeUploadResponse:
    raw = await file.read()
    try:
        document = rag.upload_document(filename=file.filename or "uploaded.txt", content=raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return KnowledgeUploadResponse(
        document=document,
        accepted_file_types=rag.supported_file_types,
        max_file_size_bytes=rag.max_upload_bytes,
    )


@router.post("/search", response_model=KnowledgeSearchResponse)
def knowledge_search(
    request: KnowledgeSearchRequest,
    rag: RAGServiceDep,
) -> KnowledgeSearchResponse:
    return rag.search(request.query, k=request.k)
