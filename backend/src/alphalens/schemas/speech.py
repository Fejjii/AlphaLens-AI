"""Schemas for speech-to-text integrations."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from alphalens.schemas.common import APIModel

SpeechProviderMode = Literal["real", "fallback"]

# Shared copy for API fallback responses and offline demo insertion (keep in sync with frontend).
SPEECH_DEMO_TRANSCRIPT = "Which policy rules are currently breached by the portfolio?"
SPEECH_FALLBACK_REASON_NO_API_KEY = (
    "OPENAI_API_KEY is not configured. Real speech transcription is unavailable."
)
SPEECH_FALLBACK_REASON_SPEECH_DISABLED = (
    "Speech is disabled (SPEECH_ENABLED=false). Real speech transcription is unavailable."
)
SPEECH_FALLBACK_TRANSCRIBE_MESSAGE = (
    "Real speech transcription is not configured. Add OPENAI_API_KEY to enable microphone transcription."
)


class TranscriptionResult(APIModel):
    request_id: str | None = None
    transcript: str = ""
    detected_language: str | None = None
    response_language: str | None = Field(default="en")
    provider_mode: SpeechProviderMode
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    fallback_reason: str | None = None
    demo_transcript: str | None = None
    message: str | None = None
    fallback_used: bool = False
    openai_called: bool = False
    openai_response_received: bool = False


class SpeechCapabilities(APIModel):
    supported_mime_types: list[str]
    max_upload_mb: int = Field(..., ge=1)
    supported_languages: list[str]
    provider_mode: SpeechProviderMode
    openai_key_configured: bool
    microphone_transcription_available: bool
    message: str
