"""Agent chat endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from alphalens.api.deps import ChatServiceDep
from alphalens.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])
public_router = APIRouter(tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, service: ChatServiceDep) -> ChatResponse:
    return service.chat(request)


@public_router.post("/chat", response_model=ChatResponse)
def public_chat(request: ChatRequest, service: ChatServiceDep) -> ChatResponse:
    """Compatibility endpoint mirroring /agent/chat."""
    return service.chat(request)
