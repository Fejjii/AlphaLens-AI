from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from httpx import AsyncClient

from alphalens.core.config import Settings
from alphalens.memory.in_memory import InMemoryMemoryStore
from alphalens.memory.sqlalchemy_memory import SqlAlchemyMemoryStore
from alphalens.memory.service import MemoryService, build_memory_store
from alphalens.infrastructure.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "How is my portfolio doing?"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    conversation_id = body["conversation_id"]
    assert conversation_id.startswith("conv_")

    memory_response = await client.get(f"/memory/{conversation_id}", headers=auth_headers)
    assert memory_response.status_code == 200
    memory_body = memory_response.json()
    assert memory_body["conversation_id"] == conversation_id
    assert len(memory_body["messages"]) == 2
    assert memory_body["messages"][0]["role"] == "user"
    assert memory_body["messages"][1]["role"] == "assistant"
    assert len(memory_body["metadata"]) == 1


async def test_memory_can_be_cleared_via_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Tell me about NVDA."}]},
        headers=auth_headers,
    )
    conversation_id = response.json()["conversation_id"]

    clear_response = await client.delete(f"/memory/{conversation_id}", headers=auth_headers)
    assert clear_response.status_code == 200
    assert clear_response.json() == {"conversation_id": conversation_id, "cleared": True}

    memory_response = await client.get(f"/memory/{conversation_id}", headers=auth_headers)
    assert memory_response.status_code == 200
    assert memory_response.json()["messages"] == []
    assert memory_response.json()["metadata"] == []


async def test_conversation_endpoints_list_and_detail(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    post = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Track this conversation please."}]},
        headers=auth_headers,
    )
    assert post.status_code == 200
    conversation_id = post.json()["conversation_id"]

    listed = await client.get("/conversations", headers=auth_headers)
    assert listed.status_code == 200
    conversations = listed.json()
    assert any(item["conversation_id"] == conversation_id for item in conversations)

    detail = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["conversation_id"] == conversation_id
    assert len(body["messages"]) >= 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"


async def test_conversation_is_user_scoped(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    first = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Private conversation."}]},
        headers=auth_headers,
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second_user = await client.post(
        "/auth/register",
        json={
            "email": "second.user@example.com",
            "password": "Password123!",
            "full_name": "Second User",
        },
    )
    assert second_user.status_code == 200
    second_headers = {"Authorization": f"Bearer {second_user.json()['access_token']}"}

    other_detail = await client.get(f"/conversations/{conversation_id}", headers=second_headers)
    assert other_detail.status_code == 404


async def test_list_conversations_excludes_empty_created_thread(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await client.post("/conversations", json={}, headers=auth_headers)
    assert created.status_code == 201
    listed = await client.get("/conversations", headers=auth_headers)
    assert listed.status_code == 200
    ids = {item["conversation_id"] for item in listed.json()}
    assert created.json()["conversation_id"] not in ids


async def test_listed_conversation_ids_are_loadable(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    for content in ("Alpha listable thread one.", "Alpha listable thread two."):
        post = await client.post(
            "/agent/chat",
            json={"messages": [{"role": "user", "content": content}]},
            headers=auth_headers,
        )
        assert post.status_code == 200
    listed = await client.get("/conversations", headers=auth_headers)
    assert listed.status_code == 200
    for item in listed.json():
        detail = await client.get(f"/conversations/{item['conversation_id']}", headers=auth_headers)
        assert detail.status_code == 200
        body = detail.json()
        assert body["conversation_id"] == item["conversation_id"]
        assert len(body["messages"]) >= 2


async def test_conversation_title_derived_from_first_user_message(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    marker = "unique_title_marker_99431"
    post = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": f"Start here {marker} and more text after."}]},
        headers=auth_headers,
    )
    assert post.status_code == 200
    conversation_id = post.json()["conversation_id"]
    listed = await client.get("/conversations", headers=auth_headers)
    row = next(item for item in listed.json() if item["conversation_id"] == conversation_id)
    assert marker in row["title"]


async def test_delete_conversation_endpoint_clears_messages(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    post = await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Delete this thread."}]},
        headers=auth_headers,
    )
    conversation_id = post.json()["conversation_id"]

    deleted = await client.delete(f"/conversations/{conversation_id}", headers=auth_headers)
    assert deleted.status_code == 204

    detail = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
    assert detail.status_code == 404


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


def test_messages_survive_sqlalchemy_store_recreation(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "memory.db"
    engine = create_engine(f"sqlite+pysqlite:///{sqlite_path}", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    store1 = SqlAlchemyMemoryStore(session_factory)
    service1 = MemoryService(store=store1, enabled=True)
    service1.save_turn(
        "conv_sqlite",
        user_id="usr_test",
        user_message={"role": "user", "content": "hello"},
        assistant_message={"role": "assistant", "content": "hi"},
        metadata={"intent": "general"},
    )

    store2 = SqlAlchemyMemoryStore(session_factory)
    service2 = MemoryService(store=store2, enabled=True)
    history = service2.get_history("conv_sqlite", user_id="usr_test")
    assert len(history["messages"]) == 2
    assert history["messages"][0]["content"] == "hello"
