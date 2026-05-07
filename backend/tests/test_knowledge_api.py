from __future__ import annotations

from httpx import AsyncClient


async def test_knowledge_stats_and_documents_include_seeded_docs(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    stats_response = await client.get("/knowledge/stats", headers=auth_headers)
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["document_count"] >= 1
    assert stats["seeded_documents"] >= 1

    docs_response = await client.get("/knowledge/documents", headers=auth_headers)
    assert docs_response.status_code == 200
    docs = docs_response.json()
    assert isinstance(docs, list)
    assert len(docs) >= 1


async def test_knowledge_upload_and_search(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    upload = await client.post(
        "/knowledge/upload",
        headers=auth_headers,
        files={
            "file": (
                "policy_note.md",
                b"# Portfolio Policy\n\nA single-name limit of 35 percent applies.\n",
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 200
    uploaded_doc = upload.json()["document"]
    assert uploaded_doc["document_title"]
    assert uploaded_doc["chunk_count"] >= 1

    search = await client.post(
        "/knowledge/search",
        headers=auth_headers,
        json={"query": "single-name limit", "k": 5},
    )
    assert search.status_code == 200
    body = search.json()
    assert body["query"] == "single-name limit"
    assert isinstance(body["results"], list)
