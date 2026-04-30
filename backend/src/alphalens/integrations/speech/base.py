"""Protocol for speech-to-text clients."""

from __future__ import annotations

from typing import Protocol

from alphalens.schemas.speech import TranscriptionResult


class SpeechError(Exception):
    """Raised when a speech provider cannot complete transcription."""


class SpeechClient(Protocol):
    def transcribe_audio(self, file_bytes: bytes, filename: str) -> TranscriptionResult:
        ...
