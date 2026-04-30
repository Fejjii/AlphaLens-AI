"""OpenAI-backed speech transcription client."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from alphalens.integrations.speech.base import SpeechClient, SpeechError
from alphalens.schemas.speech import TranscriptionResult

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI


class OpenAISpeechClient(SpeechClient):
    def __init__(self, *, api_key: str, client: OpenAI | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover
                raise SpeechError("openai package is not installed") from exc
            self._client = OpenAI(api_key=api_key)

    def transcribe_audio(self, file_bytes: bytes, filename: str) -> TranscriptionResult:
        try:
            result = self._client.audio.transcriptions.create(
                file=BytesIO(file_bytes),
                model="gpt-4o-mini-transcribe",
            )
        except Exception as exc:  # noqa: BLE001
            raise SpeechError(f"OpenAI transcription failed: {exc}") from exc
        text = getattr(result, "text", "") or ""
        language = getattr(result, "language", None)
        if not text.strip():
            raise SpeechError("OpenAI returned empty transcription")
        return TranscriptionResult(
            text=text.strip(),
            language=language,
            provider="openai",
            detected_language=language,
        )
