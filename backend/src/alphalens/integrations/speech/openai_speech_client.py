"""OpenAI-backed speech transcription client."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from alphalens.core.logging import get_logger
from alphalens.integrations.speech.base import SpeechClient, SpeechError
from alphalens.schemas.speech import TranscriptionResult

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

log = get_logger(__name__)
_DEFAULT_AUDIO_FILENAME = "recording.webm"
_MIME_TO_FILENAME = {
    "audio/webm": "recording.webm",
    "audio/ogg": "recording.ogg",
    "audio/wav": "recording.wav",
    "audio/mpeg": "recording.mp3",
    "audio/mp4": "recording.m4a",
}


def normalize_audio_content_type(raw_content_type: str | None) -> str | None:
    if not raw_content_type:
        return None
    candidate = raw_content_type.lower().split(";", 1)[0].strip()
    aliases = {
        "audio/x-wav": "audio/wav",
        "audio/mp3": "audio/mpeg",
        "audio/x-m4a": "audio/mp4",
    }
    if candidate in _MIME_TO_FILENAME:
        return candidate
    return aliases.get(candidate)


def build_openai_audio_filename(content_type: str | None, upload_filename: str | None) -> str:
    normalized = normalize_audio_content_type(content_type)
    if normalized in _MIME_TO_FILENAME:
        return _MIME_TO_FILENAME[normalized]
    clean_name = (upload_filename or "").strip()
    if "." in clean_name:
        return clean_name
    return _DEFAULT_AUDIO_FILENAME


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
        normalized_content_type = normalize_audio_content_type(content_type)
        openai_file_name = build_openai_audio_filename(
            content_type=normalized_content_type,
            upload_filename=frontend_created_filename or filename,
        )
        try:
            result = self._client.audio.transcriptions.create(
                file=(
                    openai_file_name,
                    io.BytesIO(file_bytes),
                    normalized_content_type or "application/octet-stream",
                ),
                model="gpt-4o-mini-transcribe",
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            lowered = message.lower()
            if "unsupported file format" in lowered or "unsupported_value" in lowered:
                log.warning(
                    "speech_openai_unsupported_file_format",
                    request_id=request_id,
                    openai_file_name_sent=openai_file_name,
                    openai_content_type_sent=normalized_content_type,
                )
                raise SpeechError(
                    "OpenAI rejected the uploaded audio format. "
                    "Please record/upload WEBM, OGG, WAV, MP3, or M4A."
                ) from exc
            raise SpeechError(f"OpenAI transcription failed: {exc}") from exc
        text = getattr(result, "text", "") or ""
        language = getattr(result, "language", None)
        if not text.strip():
            raise SpeechError("OpenAI returned empty transcription")
        return TranscriptionResult(
            transcript=text.strip(),
            detected_language=language,
            response_language=language or "en",
            provider_mode="real",
            confidence=0.9,
        )
