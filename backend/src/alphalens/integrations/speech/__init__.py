"""Speech integration helpers."""

from alphalens.integrations.speech.base import SpeechClient, SpeechError
from alphalens.integrations.speech.fallback_client import FallbackSpeechClient
from alphalens.integrations.speech.openai_speech_client import OpenAISpeechClient

__all__ = [
    "FallbackSpeechClient",
    "OpenAISpeechClient",
    "SpeechClient",
    "SpeechError",
]
