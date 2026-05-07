from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from alphalens.api import deps
from alphalens.api.main import create_app
from alphalens.core.config import Settings
from alphalens.integrations.speech.openai_speech_client import OpenAISpeechClient
from alphalens.integrations.speech.base import SpeechClient, SpeechError
from alphalens.integrations.speech.fallback_client import FallbackSpeechClient
from alphalens.schemas.speech import SPEECH_DEMO_TRANSCRIPT, SPEECH_FALLBACK_TRANSCRIBE_MESSAGE, TranscriptionResult
from alphalens.schemas.user import UserProfile
from alphalens.services.language_service import detect_language, get_response_language
from alphalens.services.speech_service import SpeechService


def test_speech_fallback_without_api_key() -> None:
    client = FallbackSpeechClient()

    result = client.transcribe_audio(b"fake-bytes", "sample.wav")
    assert result.provider_mode == "fallback"
    assert result.transcript == ""
    assert result.demo_transcript == SPEECH_DEMO_TRANSCRIPT
    assert result.transcript != (result.demo_transcript or "")


def test_speech_fallback_returns_stable_transcript() -> None:
    client = FallbackSpeechClient()

    first = client.transcribe_audio(b"fake-bytes", "sample.wav")
    second = client.transcribe_audio(b"fake-bytes", "sample.wav")

    assert first == second
    assert first.provider_mode == "fallback"
    assert first.detected_language == "unknown"


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
    def transcribe_audio(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        content_type: str | None = None,
        request_id: str | None = None,
        frontend_created_filename: str | None = None,
    ) -> TranscriptionResult:
        del content_type, file_bytes, filename, frontend_created_filename, request_id
        return TranscriptionResult(
            transcript="hello from audio",
            detected_language="en",
            response_language="en",
            provider_mode="real",
            confidence=0.8,
        )


class _FailingSpeechClient(SpeechClient):
    def transcribe_audio(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        content_type: str | None = None,
        request_id: str | None = None,
        frontend_created_filename: str | None = None,
    ) -> TranscriptionResult:
        del content_type, file_bytes, filename, frontend_created_filename, request_id
        raise SpeechError("OpenAI transcription failed: simulated outage")


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
    speech_app,
    auth_headers: dict[str, str],
) -> None:
    speech_app.state.settings.openai_api_key = "sk-test-stub"
    files = {"file": ("sample.wav", b"RIFF....WAVEfmt ", "audio/wav")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider_mode"] == "real"
    assert body["transcript"] == "hello from audio"
    assert body["detected_language"] == "en"


async def test_speech_endpoint_fallback_without_openai_key(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    files = {"file": ("recording.webm", b"\x1a\x45\xdf\xa3fake-webm", "audio/webm;codecs=opus")}
    response = await client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider_mode"] == "fallback"
    assert body["transcript"] == ""
    assert body["demo_transcript"] == SPEECH_DEMO_TRANSCRIPT
    assert body["transcript"] != body["demo_transcript"]
    assert body["confidence"] == 0
    assert body["detected_language"] == "unknown"
    assert body["fallback_used"] is True
    assert body["openai_called"] is False
    assert body["message"] == SPEECH_FALLBACK_TRANSCRIBE_MESSAGE


async def test_speech_fallback_bypasses_plan_limit() -> None:
    app = create_app(Settings())

    class _FailingPlanService:
        def ensure_usage_allowed(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("plan limit should not be checked in fallback mode")

    app.dependency_overrides[deps.get_plan_service] = lambda: _FailingPlanService()
    app.dependency_overrides[deps.get_current_user] = lambda: UserProfile(
        id="usr_demo",
        email="demo@alphalens.ai",
        full_name="Demo User",
        role="user",
        plan="free",
        is_active=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        reg = await ac.post(
            "/auth/register",
            json={
                "email": f"speech.fallback.plan.{uuid.uuid4().hex[:10]}@example.com",
                "password": "Password123!",
                "full_name": "Plan Test",
            },
        )
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = await ac.post(
            "/speech/transcribe",
            files={"file": ("recording.webm", b"\x1a\x45\xdf\xa3fake-webm", "audio/webm;codecs=opus")},
            headers=headers,
        )
    assert response.status_code == 200
    body = response.json()
    assert body["provider_mode"] == "fallback"
    assert body["transcript"] == ""
    assert body["openai_called"] is False


async def test_speech_capabilities_endpoint_defaults(
    speech_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await speech_client.get("/speech/capabilities", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["supported_mime_types"] == [
        "audio/webm",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/x-m4a",
    ]
    assert body["max_upload_mb"] == 25
    assert body["supported_languages"] == ["en", "de", "fr", "ar"]
    assert body["provider_mode"] == "fallback"
    assert body["openai_key_configured"] is False
    assert body["microphone_transcription_available"] is False
    assert isinstance(body["message"], str) and body["message"]


async def test_speech_capabilities_endpoint_real_mode_when_key_configured(
    speech_client: AsyncClient,
    speech_app,
    auth_headers: dict[str, str],
) -> None:
    speech_app.state.settings.openai_api_key = "test-openai-key"
    response = await speech_client.get("/speech/capabilities", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["provider_mode"] == "real"
    assert data["openai_key_configured"] is True
    assert data["microphone_transcription_available"] is True


async def test_speech_capabilities_without_auth_returns_200(client: AsyncClient) -> None:
    """Capability metadata is public so clients can probe speech support without a session."""
    response = await client.get("/speech/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["provider_mode"] in {"real", "fallback"}
    assert isinstance(body["openai_key_configured"], bool)


async def test_speech_capabilities_never_serializes_openai_secret(
    speech_client: AsyncClient,
    speech_app,
) -> None:
    secret = "sk-capabilities-response-must-never-contain-this-unique-value"
    speech_app.state.settings.openai_api_key = secret
    response = await speech_client.get("/speech/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert "openai_api_key" not in payload
    assert secret not in response.text
    assert all(secret not in str(value) for value in payload.values())


async def test_speech_transcribe_without_auth_returns_401(client: AsyncClient) -> None:
    files = {"file": ("recording.webm", b"\x1a\x45\xdf\xa3fake-webm", "audio/webm;codecs=opus")}
    response = await client.post("/speech/transcribe", files=files)
    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert isinstance(detail, str)
    assert "credentials were not provided" in detail.lower()


async def test_speech_endpoint_real_provider_error_returns_503() -> None:
    app = create_app(Settings())
    app.state.settings.openai_api_key = "sk-real-mode-test"
    app.dependency_overrides[deps.get_speech_service] = lambda: SpeechService(
        client=_FailingSpeechClient()
    )
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        reg = await ac.post(
            "/auth/register",
            json={
                "email": f"speech.503.{uuid.uuid4().hex[:10]}@example.com",
                "password": "Password123!",
                "full_name": "Speech 503",
            },
        )
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        response = await ac.post(
            "/speech/transcribe",
            files={"file": ("sample.wav", b"RIFF....WAVEfmt ", "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "speech_provider_unavailable"


async def test_speech_endpoint_unsupported_format_maps_to_useful_503_message() -> None:
    class _UnsupportedFormatSpeechClient(SpeechClient):
        def transcribe_audio(
            self,
            file_bytes: bytes,
            filename: str,
            *,
            content_type: str | None = None,
            request_id: str | None = None,
            frontend_created_filename: str | None = None,
        ) -> TranscriptionResult:
            del content_type, file_bytes, filename, frontend_created_filename, request_id
            raise SpeechError(
                "OpenAI rejected the uploaded audio format. "
                "Please record/upload WEBM, OGG, WAV, MP3, or M4A."
            )

    app = create_app(Settings())
    app.state.settings.openai_api_key = "sk-real-mode-test"
    app.dependency_overrides[deps.get_speech_service] = lambda: SpeechService(
        client=_UnsupportedFormatSpeechClient()
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        reg = await ac.post(
            "/auth/register",
            json={
                "email": f"speech.503.format.{uuid.uuid4().hex[:10]}@example.com",
                "password": "Password123!",
                "full_name": "Speech 503 Format",
            },
        )
        token = reg.json()["access_token"]
        response = await ac.post(
            "/speech/transcribe",
            files={"file": ("sample.wav", b"RIFF....WAVEfmt ", "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "speech_provider_unavailable"
    assert "uploaded audio format" in detail["message"]


async def test_speech_endpoint_invalid_mime_type(
    speech_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    files = {"file": ("sample.txt", b"hello", "text/plain")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "unsupported_audio_type"
    assert body["detail"]["received_content_type"] == "text/plain"
    assert "audio/webm" in body["detail"]["supported_content_types"]
    assert "Browser microphone usually records audio/webm;codecs=opus." in body["detail"]["hint"]


async def test_speech_endpoint_accepts_audio_alias_mime_type(
    speech_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    files = {"file": ("sample.wav", b"RIFF....WAVEfmt ", "audio/x-wav")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 200


async def test_speech_endpoint_accepts_webm_with_codecs_suffix(
    speech_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    files = {"file": ("recording.webm", b"\x1a\x45\xdf\xa3fake-webm", "audio/webm;codecs=opus")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 200


async def test_speech_endpoint_normalizes_webm_codecs_for_service() -> None:
    class _CaptureSpeechClient(SpeechClient):
        def __init__(self) -> None:
            self.content_type: str | None = None
            self.filename: str | None = None

        def transcribe_audio(
            self,
            file_bytes: bytes,
            filename: str,
            *,
            content_type: str | None = None,
            request_id: str | None = None,
            frontend_created_filename: str | None = None,
        ) -> TranscriptionResult:
            del file_bytes, request_id, frontend_created_filename
            self.content_type = content_type
            self.filename = filename
            return TranscriptionResult(
                transcript="ok",
                detected_language="en",
                response_language="en",
                provider_mode="real",
                confidence=0.9,
            )

    settings = Settings()
    settings.openai_api_key = "sk-real-mode"
    app = create_app(settings)
    capture = _CaptureSpeechClient()
    app.dependency_overrides[deps.get_speech_service] = lambda: SpeechService(client=capture)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        reg = await ac.post(
            "/auth/register",
            json={
                "email": f"speech.normalize.{uuid.uuid4().hex[:10]}@example.com",
                "password": "Password123!",
                "full_name": "Speech Normalize",
            },
        )
        token = reg.json()["access_token"]
        response = await ac.post(
            "/speech/transcribe",
            files={"file": ("recording.webm", b"\x1a\x45\xdf\xa3fake-webm", "audio/webm;codecs=opus")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert capture.content_type == "audio/webm"
    assert capture.filename == "recording.webm"


async def test_speech_endpoint_rejects_empty_audio(
    speech_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    files = {"file": ("recording.wav", b"", "audio/wav")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "empty_audio_file"


async def test_speech_endpoint_oversized_file(
    speech_client: AsyncClient,
    speech_app,
    auth_headers: dict[str, str],
) -> None:
    speech_app.state.settings.speech_max_upload_bytes = 1
    files = {"file": ("sample.wav", b"too-big", "audio/wav")}
    response = await speech_client.post("/speech/transcribe", files=files, headers=auth_headers)
    assert response.status_code == 400


async def test_speech_transcribe_quota_exceeded_returns_429_without_transcription() -> None:
    deps.get_usage_service().reset()

    class _ProbeSpeechClient(SpeechClient):
        def __init__(self) -> None:
            self.calls = 0

        def transcribe_audio(
            self,
            file_bytes: bytes,
            filename: str,
            *,
            content_type: str | None = None,
            request_id: str | None = None,
            frontend_created_filename: str | None = None,
        ) -> TranscriptionResult:  # noqa: ARG002
            del content_type, frontend_created_filename, request_id
            self.calls += 1
            return TranscriptionResult(
                transcript="should-not-run",
                detected_language="en",
                response_language="en",
                provider_mode="real",
                confidence=0.99,
            )

    probe = _ProbeSpeechClient()

    settings = Settings()
    settings.openai_api_key = "sk-quota-integration-test-key"
    settings.app_env = "test"
    settings.dev_bypass_quotas = False
    app = create_app(settings)
    app.dependency_overrides[deps.get_speech_service] = lambda: SpeechService(client=probe)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            email = f"speech.quota.{uuid.uuid4().hex[:12]}@example.com"
            reg = await ac.post(
                "/auth/register",
                json={
                    "email": email,
                    "password": "Password123!",
                    "full_name": "Speech Quota",
                },
            )
            assert reg.status_code == 200
            uid = reg.json()["user"]["id"]
            token = reg.json()["access_token"]

            usage = deps.get_usage_service()
            for _ in range(5):
                usage.record_event(
                    event_type="speech_uploaded",
                    provider="test",
                    user_id=uid,
                )

            speech_before = sum(
                1 for ev in usage.list_usage_events(user_id=uid) if ev.event_type == "speech_uploaded"
            )
            assert speech_before == 5

            response = await ac.post(
                "/speech/transcribe",
                files={"file": ("sample.wav", b"RIFF....WAVEfmt ", "audio/wav")},
                headers={"Authorization": f"Bearer {token}"},
            )
            speech_after = sum(
                1 for ev in usage.list_usage_events(user_id=uid) if ev.event_type == "speech_uploaded"
            )

            assert response.status_code == 429
            assert speech_before == speech_after == 5
            assert probe.calls == 0

            body = response.json()["detail"]
            assert body["error"] == "quota_exceeded"
            assert body["feature"] == "speech_uploads"
            assert body["plan"] == "free"
            assert body["limit"] == 5
            assert body["used"] == 5
            assert isinstance(body["reset_at"], str) and len(body["reset_at"]) >= 10
            assert "limit reached" in str(body["message"]).lower()

    finally:
        app.dependency_overrides.pop(deps.get_speech_service, None)
        deps.get_usage_service().reset()


def test_openai_client_sends_webm_filename_with_extension() -> None:
    class _FakeTranscriptions:
        def __init__(self) -> None:
            self.payload = None

        def create(self, **kwargs):  # type: ignore[no-untyped-def]
            self.payload = kwargs
            return type("Resp", (), {"text": "ok", "language": "en"})()

    fake = _FakeTranscriptions()
    fake_openai = type(
        "FakeOpenAI",
        (),
        {"audio": type("FakeAudio", (), {"transcriptions": fake})()},
    )()
    client = OpenAISpeechClient(api_key="sk-test", client=fake_openai)  # type: ignore[arg-type]
    result = client.transcribe_audio(
        b"\x1a\x45\xdf\xa3fake-webm",
        "tmp-upload",
        content_type="audio/webm;codecs=opus",
    )
    assert result.transcript == "ok"
    assert isinstance(fake.payload, dict)
    sent_file = fake.payload["file"]
    assert sent_file[0].endswith(".webm")
    assert sent_file[1].__class__.__name__ == "BytesIO"
    assert sent_file[2] == "audio/webm"


def test_openai_client_sends_expected_extensions_for_common_mime_types() -> None:
    class _FakeTranscriptions:
        def __init__(self) -> None:
            self.payload = None

        def create(self, **kwargs):  # type: ignore[no-untyped-def]
            self.payload = kwargs
            return type("Resp", (), {"text": "ok", "language": "en"})()

    for content_type, extension in [
        ("audio/ogg", ".ogg"),
        ("audio/wav", ".wav"),
    ]:
        fake = _FakeTranscriptions()
        fake_openai = type(
            "FakeOpenAI",
            (),
            {"audio": type("FakeAudio", (), {"transcriptions": fake})()},
        )()
        client = OpenAISpeechClient(api_key="sk-test", client=fake_openai)  # type: ignore[arg-type]
        client.transcribe_audio(b"fake-audio", "upload.bin", content_type=content_type)
        assert isinstance(fake.payload, dict)
        sent_file = fake.payload["file"]
        assert sent_file[0].endswith(extension)


def test_openai_client_maps_unsupported_format_error_to_speech_error() -> None:
    class _FakeTranscriptions:
        def create(self, **kwargs):  # type: ignore[no-untyped-def]
            del kwargs
            raise RuntimeError("400 Unsupported file format unsupported_value")

    fake_openai = type(
        "FakeOpenAI",
        (),
        {"audio": type("FakeAudio", (), {"transcriptions": _FakeTranscriptions()})()},
    )()
    client = OpenAISpeechClient(api_key="sk-test", client=fake_openai)  # type: ignore[arg-type]
    with pytest.raises(SpeechError, match="OpenAI rejected the uploaded audio format"):
        client.transcribe_audio(b"bad-data", "tmpfile", content_type="audio/webm")
