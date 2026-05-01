from __future__ import annotations

from httpx import AsyncClient

from alphalens.api import deps
from alphalens.schemas.feedback import FeedbackCategory, FeedbackCreate, FeedbackRating
from alphalens.services.feedback_service import FeedbackService


def test_feedback_service_summarizes_records() -> None:
    service = FeedbackService()
    service.create_feedback(
        FeedbackCreate(
            conversation_id="conv_1",
            response_id="msg_1",
            rating=FeedbackRating.THUMBS_UP,
            category=FeedbackCategory.USEFULNESS,
        ),
        user_id="usr_feedback_test",
    )
    service.create_feedback(
        FeedbackCreate(
            conversation_id="conv_1",
            response_id="msg_2",
            rating=FeedbackRating.THUMBS_DOWN,
            category=FeedbackCategory.ACCURACY,
        ),
        user_id="usr_feedback_test",
    )

    summary = service.summarize_feedback(user_id="usr_feedback_test")

    assert summary.total_feedback == 2
    assert summary.thumbs_up == 1
    assert summary.thumbs_down == 1
    assert summary.by_category == {"accuracy": 1, "usefulness": 1}


async def test_feedback_api_roundtrip(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/feedback",
        json={
            "conversation_id": "conv_1",
            "response_id": "msg_1",
            "rating": "thumbs_up",
            "comment": "Helpful",
            "category": "clarity",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"].startswith("fdb_")
    assert body["rating"] == "thumbs_up"
    assert body["category"] == "clarity"

    list_response = await client.get("/feedback", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    summary_response = await client.get("/feedback/summary", headers=auth_headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["total_feedback"] == 1
    assert summary["thumbs_up"] == 1
    assert summary["thumbs_down"] == 0


async def test_feedback_service_records_usage_event() -> None:
    deps._feedback_service.cache_clear()
    deps._usage_service.cache_clear()
    service = deps.get_feedback_service()
    usage = deps.get_usage_service()
    service.reset()
    usage.reset()

    service.create_feedback(
        FeedbackCreate(
            conversation_id="conv_2",
            response_id="msg_2",
            rating=FeedbackRating.THUMBS_DOWN,
        ),
        user_id="usr_feedback_usage",
    )

    events = usage.list_usage_events()
    assert len(events) == 1
    assert events[0].event_type == "feedback_submitted"
