"""Deterministic speech fallback client (no external STT)."""

from __future__ import annotations

from alphalens.integrations.speech.base import SpeechClient, SpeechError
from alphalens.schemas.speech import (
    SPEECH_DEMO_TRANSCRIPT,
    SPEECH_FALLBACK_REASON_NO_API_KEY,
    TranscriptionResult,
)


class FallbackSpeechClient(SpeechClient):
    """Returns empty transcript plus demo text; does not impersonate real STT."""

    def __init__(self, *, mock_text: str | None = None) -> None:
        self._mock_text = mock_text

    def transcribe_audio(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        content_type: str | None = None,
        request_id: str | None = None,
        frontend_created_filename: str | None = None,
    ) -> TranscriptionResult:
        if not file_bytes:
            raise SpeechError("Audio payload is empty.")
        del content_type, filename, frontend_created_filename, request_id
        demo = self._mock_text if self._mock_text is not None else SPEECH_DEMO_TRANSCRIPT
        return TranscriptionResult(
            transcript="",
            detected_language="unknown",
            response_language="en",
            provider_mode="fallback",
            confidence=0.0,
            fallback_reason=SPEECH_FALLBACK_REASON_NO_API_KEY,
            demo_transcript=demo,
        )
