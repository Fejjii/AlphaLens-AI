from __future__ import annotations

import pytest
from httpx import AsyncClient

from alphalens.api import deps
from alphalens.api.main import create_app
from alphalens.core.config import Settings
from alphalens.integrations.speech.base import SpeechClient
from alphalens.integrations.speech.fallback_client import FallbackSpeechClient
from alphalens.schemas.speech import TranscriptionResult
from alphalens.services.language_service import detect_language, get_response_language
from alphalens.services.speech_service import SpeechService


def test_speech_fallback_without_api_key() -> None:
    client = FallbackSpeechClient()

    result = client.transcribe_audio(b"fake-bytes", "sample.wav")
    assert result.provider == "fallback"
    assert result.text.startswith("Transcription unavailable.")


def test_speech_fallback_returns_stable_transcript() -> None:
    client = FallbackSpeechClient()

    first = client.transcribe_audio(b"fake-bytes", "sample.wav")
    second = client.transcribe_audio(b"fake-bytes", "sample.wav")

    assert first == second
    assert first.provider == "fallback"
    assert first.detected_language == "en"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello, how are you?", "en"),
        ("Was ist mit meinem Portfolio und der Bank?", "de"),
        ("Bonjour, comment va mon portefeuille et le marché?", "fr"),
        ("مرحبا كيف حال السوق", "ar"),
    ],
)
def test_language_detection(text: str, expected: str) -> None:
    assert detect_language(text) == expected


def test_response_language_prefers_user_preference() -> None:
    assert get_response_language("Hello", "de") == "de"


def test_response_language_defaults_when_detection_is_uncertain() -> None:
    assert get_response_language("12345", "auto", default_language="fr") == "fr"


class _StubSpeechClient(SpeechClient):
    def transcribe_audio(self, file_bytes: bytes, filename: str) -> TranscriptionResult:
        return TranscriptionResult(
            text="hello from audio",
            language="en",
            provider="stub",
            detected_language="en",
        )


@pytest.fixture
def speech_app():
    app = create_app(Settings())
    app.dependency_overrides[deps.get_speech_service] = lambda: SpeechService(
        client=_StubSpeechClient()
    )
    return app


@pytest.fixture
async def speech_client(speech_app) -> AsyncClient:
    from httpx import ASGITransport

    transport = ASGITransport(app=speech_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def test_speech_endpoint_validation(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post("/speech/transcribe", headers=auth_headers)
    assert response.status_code == 422


async def test_speech_endpoint_valid_audio_upload(
    speech_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    files = {"file": ("sample.wav", b"RIFF....WAVEfmt ", "audio/wav")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "stub"
    assert body["text"] == "hello from audio"
    assert body["detected_language"] == "en"


async def test_speech_endpoint_invalid_mime_type(
    speech_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    files = {"file": ("sample.txt", b"hello", "text/plain")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 400


async def test_speech_endpoint_oversized_file(
    speech_client: AsyncClient,
    speech_app,
    auth_headers: dict[str, str],
) -> None:
    speech_app.state.settings.speech_max_upload_bytes = 1
    files = {"file": ("sample.wav", b"too-big", "audio/wav")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 400
