"""Speech service: selects OpenAI transcription (real STT only; no silent demo fallback)."""

from __future__ import annotations

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger
from alphalens.integrations.speech import FallbackSpeechClient, OpenAISpeechClient, SpeechClient
from alphalens.integrations.speech.base import SpeechError
from alphalens.schemas.speech import TranscriptionResult

logger = get_logger(__name__)


class SpeechService:
    def __init__(self, *, client: SpeechClient) -> None:
        self._client = client

    @property
    def speech_client_class_name(self) -> str:
        return self._client.__class__.__name__

    def transcribe_audio(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        content_type: str | None = None,
        request_id: str | None = None,
        frontend_created_filename: str | None = None,
    ) -> TranscriptionResult:
        return self._client.transcribe_audio(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            request_id=request_id,
            frontend_created_filename=frontend_created_filename,
        )


def get_speech_client(settings: Settings) -> SpeechClient:
    if settings.speech_enabled and settings.openai_api_key:
        try:
            return OpenAISpeechClient(api_key=settings.openai_api_key)
        except SpeechError:
            logger.warning("speech_client_init_fallback", provider="openai")
    return FallbackSpeechClient()


def get_speech_service(settings: Settings) -> SpeechService:
    return SpeechService(client=get_speech_client(settings))
