"""Agent chat endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from alphalens.api.deps import ChatServiceDep, CurrentUserDep, PlanServiceDep, UsageServiceDep
from alphalens.api.rate_limit import rate_limit_request
from alphalens.core.config import get_settings
from alphalens.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])
public_router = APIRouter(tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    http_request: Request,
    service: ChatServiceDep,
    current_user: CurrentUserDep,
    plans: PlanServiceDep,
    usage: UsageServiceDep,
) -> ChatResponse:
    plans.ensure_usage_allowed(current_user, "chats")
    rate_limit_request(http_request, route="chat", subject=current_user.id, settings=get_settings())
    request_id = http_request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
    response = service.chat(
        request,
        user=current_user,
        request_id=request_id,
        endpoint="/agent/chat",
    )
    usage.record_event(
        event_type="llm_call",
        provider="agent",
        user_id=current_user.id,
        conversation_id=response.conversation_id,
        metadata={"operation": "chat"},
    )
    usage.record_tool_usage(
        tool_name="agent_chat",
        success=True,
        provider="agent",
        user_id=current_user.id,
        conversation_id=response.conversation_id,
        metadata={"operation": "chat"},
    )
    return response


@public_router.post("/chat", response_model=ChatResponse)
def public_chat(
    request: ChatRequest,
    http_request: Request,
    service: ChatServiceDep,
    current_user: CurrentUserDep,
    plans: PlanServiceDep,
    usage: UsageServiceDep,
) -> ChatResponse:
    """Compatibility endpoint mirroring /agent/chat."""
    plans.ensure_usage_allowed(current_user, "chats")
    rate_limit_request(http_request, route="chat", subject=current_user.id, settings=get_settings())
    request_id = http_request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
    response = service.chat(
        request,
        user=current_user,
        request_id=request_id,
        endpoint="/chat",
    )
    usage.record_event(
        event_type="llm_call",
        provider="agent",
        user_id=current_user.id,
        conversation_id=response.conversation_id,
        metadata={"operation": "chat"},
    )
    usage.record_tool_usage(
        tool_name="agent_chat",
        success=True,
        provider="agent",
        user_id=current_user.id,
        conversation_id=response.conversation_id,
        metadata={"operation": "chat"},
    )
    return response
