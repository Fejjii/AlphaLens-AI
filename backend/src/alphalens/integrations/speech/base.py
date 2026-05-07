"""Protocol for speech-to-text clients."""

from __future__ import annotations

from typing import Protocol

from alphalens.schemas.speech import TranscriptionResult


class SpeechError(Exception):
    """Raised when a speech provider cannot complete transcription."""


class SpeechClient(Protocol):
    def transcribe_audio(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        content_type: str | None = None,
        request_id: str | None = None,
        frontend_created_filename: str | None = None,
    ) -> TranscriptionResult:
        ...
