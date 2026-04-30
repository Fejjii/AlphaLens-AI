"""Speech service: selects OpenAI transcription or a deterministic fallback."""

from __future__ import annotations

import hashlib

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger
from alphalens.integrations.speech import FallbackSpeechClient, OpenAISpeechClient, SpeechClient
from alphalens.integrations.speech.base import SpeechError
from alphalens.schemas.speech import TranscriptionResult

logger = get_logger(__name__)


class SpeechService:
    def __init__(self, *, client: SpeechClient, fallback_client: SpeechClient | None = None) -> None:
        self._client = client
        self._fallback_client = fallback_client or FallbackSpeechClient()

    def transcribe_audio(self, file_bytes: bytes, filename: str) -> TranscriptionResult:
        try:
            return self._client.transcribe_audio(file_bytes=file_bytes, filename=filename)
        except SpeechError as exc:
            if isinstance(self._client, FallbackSpeechClient):
                raise
            logger.warning("speech_provider_fallback", provider="openai", error=str(exc))
            return self._fallback_client.transcribe_audio(
                file_bytes=file_bytes, filename=filename
            )


def _stable_transcript(file_bytes: bytes, filename: str) -> str:
    digest = hashlib.sha256(file_bytes + filename.encode("utf-8")).hexdigest()[:12]
    return f"Transcription unavailable. Reference: {digest}."


def get_speech_client(settings: Settings) -> SpeechClient:
    if settings.speech_enabled and settings.openai_api_key:
        try:
            return OpenAISpeechClient(api_key=settings.openai_api_key)
        except SpeechError:
            logger.warning("speech_client_init_fallback", provider="openai")
    return FallbackSpeechClient()


def get_speech_service(settings: Settings) -> SpeechService:
    return SpeechService(client=get_speech_client(settings))
