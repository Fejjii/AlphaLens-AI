"""LLM clients used by the agent.

A small protocol with two methods (`classify_intent`, `synthesize_decision`)
so the OpenAI-backed and deterministic implementations are interchangeable
and easy to test.
"""

from alphalens.integrations.llm.base import LLMClient, LLMError
from alphalens.integrations.llm.fallback_client import DeterministicFallbackLLMClient
from alphalens.integrations.llm.openai_client import OpenAILLMClient

__all__ = [
    "LLMClient",
    "LLMError",
    "DeterministicFallbackLLMClient",
    "OpenAILLMClient",
]
