from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from httpx import AsyncClient

from alphalens.core.config import Settings
from alphalens.memory.in_memory import InMemoryMemoryStore
from alphalens.memory.service import MemoryService, build_memory_store
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.rag_service import RAGService
from alphalens.tools.registry import ToolRegistry


def _build_chat_service(
    *,
    tmp_path: Path,
    memory_service: MemoryService | None,
) -> ChatService:
    settings = Settings(
        knowledge_base_path=str(tmp_path / "kb"),
        rag_collection=f"memory_test_{tmp_path.name}",
    )
    kb_dir = Path(settings.knowledge_base_path)
    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "note.md").write_text("# Note\n\nMemory test fixture.\n", encoding="utf-8")
    return ChatService(
        settings=settings,
        rag_service=RAGService(settings),
        approvals_service=ApprovalsService(),
        registry=ToolRegistry(),
        memory_service=memory_service,
    )


class _CapturingGraph:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def invoke(self, state: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append({"state": state, "config": config})
        last_user = next(
            (
                str(message.get("content", ""))
                for message in reversed(state.get("messages", []))
                if message.get("role") == "user"
            ),
            "",
        )
        return {
            "intent": "general",
            "recommendation": "inform",
            "reasoning": ["ok"],
            "evidence": [],
            "requires_approval": False,
            "risk_level": "low",
            "confidence": 0.7,
            "answer": f"Echo: {last_user}",
            "used_tools": [],
            "citations": [],
        }


async def test_first_chat_creates_conversation_id_and_persists_memory(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "How is my portfolio doing?"}]},
    )
    assert response.status_code == 200
    body = response.json()
    conversation_id = body["conversation_id"]
    assert conversation_id.startswith("conv_")

    memory_response = await client.get(f"/memory/{conversation_id}")
    assert memory_response.status_code == 200
    memory_body = memory_response.json()
    assert memory_body["conversation_id"] == conversation_id
    assert len(memory_body["messages"]) == 2
    assert memory_body["messages"][0]["role"] == "user"
    assert memory_body["messages"][1]["role"] == "assistant"
    assert len(memory_body["metadata"]) == 1


async def test_memory_can_be_cleared_via_api(client: AsyncClient) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Tell me about NVDA."}]},
    )
    conversation_id = response.json()["conversation_id"]

    clear_response = await client.delete(f"/memory/{conversation_id}")
    assert clear_response.status_code == 200
    assert clear_response.json() == {"conversation_id": conversation_id, "cleared": True}

    memory_response = await client.get(f"/memory/{conversation_id}")
    assert memory_response.status_code == 200
    assert memory_response.json()["messages"] == []
    assert memory_response.json()["metadata"] == []


def test_second_chat_with_same_conversation_id_sees_previous_messages(
    tmp_path: Path,
) -> None:
    memory = MemoryService(store=InMemoryMemoryStore(ttl_seconds=3600), enabled=True)
    service = _build_chat_service(tmp_path=tmp_path, memory_service=memory)
    graph = _CapturingGraph()
    service._graph = graph

    first = service.chat(
        ChatRequest(
            messages=[ChatMessage(role=ChatRole.USER, content="Let's discuss NVDA.")],
        )
    )
    second = service.chat(
        ChatRequest(
            conversation_id=first.conversation_id,
            messages=[ChatMessage(role=ChatRole.USER, content="What about tomorrow?")],
        )
    )

    assert second.conversation_id == first.conversation_id
    assert len(graph.calls) == 2
    second_state = graph.calls[1]["state"]
    messages = second_state["messages"]
    assert len(messages) == 3
    assert messages[0]["content"] == "Let's discuss NVDA."
    assert messages[1]["role"] == "assistant"
    assert messages[2]["content"] == "What about tomorrow?"
    assert second_state["conversation_history"][0]["content"] == "Let's discuss NVDA."
    assert graph.calls[1]["config"] == {
        "configurable": {"thread_id": first.conversation_id}
    }


def test_memory_disabled_does_not_persist(tmp_path: Path) -> None:
    memory = MemoryService(store=InMemoryMemoryStore(ttl_seconds=3600), enabled=False)
    service = _build_chat_service(tmp_path=tmp_path, memory_service=memory)
    service._graph = _CapturingGraph()

    response = service.chat(
        ChatRequest(messages=[ChatMessage(role=ChatRole.USER, content="Hello there")])
    )
    assert response.conversation_id.startswith("conv_")
    assert service.get_memory(response.conversation_id) == {"messages": [], "metadata": []}


def test_in_memory_memory_ttl_expiry_works() -> None:
    store = InMemoryMemoryStore(ttl_seconds=1)
    service = MemoryService(store=store, enabled=True)
    service.save_turn(
        "conv_ttl",
        user_message={"role": "user", "content": "hi"},
        assistant_message={"role": "assistant", "content": "hello"},
        metadata={"intent": "general"},
    )
    assert len(service.get_history("conv_ttl")["messages"]) == 2
    time.sleep(1.05)
    assert service.get_history("conv_ttl") == {"messages": [], "metadata": []}


def test_redis_unavailable_falls_back_safely() -> None:
    settings = Settings(
        MEMORY_ENABLED=True,
        MEMORY_BACKEND="redis",
        MEMORY_TTL_SECONDS=3600,
        REDIS_URL="redis://127.0.0.1:65500/0",
    )
    store = build_memory_store(settings)
    service = MemoryService(store=store, enabled=True)

    service.save_turn(
        "conv_redis",
        user_message={"role": "user", "content": "hi"},
        assistant_message={"role": "assistant", "content": "hello"},
        metadata={"intent": "general"},
    )
    history = service.get_history("conv_redis")
    assert len(history["messages"]) == 2
    assert history["messages"][0]["content"] == "hi"
