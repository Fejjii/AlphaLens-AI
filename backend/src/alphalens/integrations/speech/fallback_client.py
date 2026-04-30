"""Deterministic speech fallback used in tests and offline environments."""

from __future__ import annotations

import hashlib

from alphalens.integrations.speech.base import SpeechClient, SpeechError
from alphalens.schemas.speech import TranscriptionResult


class FallbackSpeechClient(SpeechClient):
    def __init__(self, *, mock_text: str | None = None) -> None:
        self._mock_text = mock_text

    def transcribe_audio(self, file_bytes: bytes, filename: str) -> TranscriptionResult:
        if self._mock_text is not None:
            text = self._mock_text
        else:
            digest = hashlib.sha256(file_bytes + filename.encode("utf-8")).hexdigest()[:12]
            text = f"Transcription unavailable. Reference: {digest}."
        return TranscriptionResult(
            text=text,
            language="en",
            provider="fallback",
            detected_language="en",
        )
