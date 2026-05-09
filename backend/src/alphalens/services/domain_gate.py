"""Localized short replies for domain-gated chat turns.

Domain classification lives in ``chat_domain_router``; this module keeps
user-facing copy and a tiny compatibility shim for tests.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from alphalens.core.config import get_settings
from alphalens.schemas.agent import ChatAnswerType
from alphalens.services.chat_domain_router import resolve_chat_route


class ChatAnswerDomain(str, Enum):
    """Legacy three-way routing bucket (tests / older call sites)."""

    INVESTMENT_AGENT_TASK = "investment_agent_task"
    APP_HELP_OR_CAPABILITY = "app_help_or_capability_question"
    OUT_OF_SCOPE_GENERAL = "out_of_scope_general"


def classify_chat_domain(
    user_text: str,
    *,
    prior_messages: list[dict[str, Any]] | None = None,
) -> ChatAnswerDomain:
    """Best-effort mapping of the layered router into the legacy enum."""
    settings = get_settings()
    route = resolve_chat_route(
        user_text,
        prior_messages=prior_messages or [],
        detected_language="en",
        confidence_threshold=settings.chat_router_confidence_threshold,
        llm_classify=None,
    )
    if route.answer_type == ChatAnswerType.INVESTMENT_DECISION.value:
        return ChatAnswerDomain.INVESTMENT_AGENT_TASK
    if route.answer_type == ChatAnswerType.OUT_OF_SCOPE.value:
        return ChatAnswerDomain.OUT_OF_SCOPE_GENERAL
    return ChatAnswerDomain.APP_HELP_OR_CAPABILITY


def app_help_reply(response_language: str) -> str:
    lang = (response_language or "en").lower().split("-", 1)[0]
    if lang == "fr":
        return (
            "Oui, je comprends le français et je peux répondre en français. "
            "Pour AlphaLens AI, je peux vous aider à analyser le portefeuille, "
            "les règles et le risque, les documents internes (RAG), "
            "l’actualité marché, les validations, les rapports et les scénarios."
        )
    if lang == "de":
        return (
            "Ja — ich kann Deutsch verstehen und auf Deutsch antworten. "
            "Mit AlphaLens AI helfe ich bei Portfolioanalyse, Risiko- und Policy-Checks, "
            "internen Dokumenten (RAG), Markt-/News-Kontext, Freigaben, Reports und Szenarien."
        )
    if lang == "ar":
        return (
            "نعم — يمكنني فهم العربية والرد بها عند الحاجة. "
            "في AlphaLens AI أساعدك في تحليل المحفظة، والسياسات والمخاطر، "
            "والمستندات الداخلية (RAG)، وأخبار السوق، والموافقات، والتقارير، والسيناريوهات."
        )
    return (
        "Yes — I can answer in multiple languages when you write in them. "
        "For AlphaLens AI, I help with portfolio analysis, policy and risk checks, "
        "internal documents (RAG), market and news context, approvals, reports, and scenarios."
    )


def out_of_scope_reply(response_language: str) -> str:
    lang = (response_language or "en").lower().split("-", 1)[0]
    if lang == "fr":
        return (
            "Je suis optimisé pour les workflows d’investissement AlphaLens : "
            "analyse de portefeuille, contrôles de politique et de risque, RAG sur les documents internes, "
            "contexte marché/actualités, validations, rapports et scénarios. "
            "Posez-moi une question dans l’un de ces domaines."
        )
    if lang == "de":
        return (
            "Ich bin auf AlphaLens-Investment-Workflows ausgelegt: Portfolioanalyse, Policy- und Risiko-Checks, "
            "RAG über interne Dokumente, Markt-/News-Kontext, Freigaben, Reports und Szenarien. "
            "Bitte stellen Sie eine Frage zu einem dieser Themen."
        )
    if lang == "ar":
        return (
            "أنا مُحسَّن لمسارات عمل الاستثمار في AlphaLens: تحليل المحفظة، "
            "فحص السياسات والمخاطر، RAG على المستندات الداخلية، سياق السوق والأخبار، "
            "الموافقات، التقارير، والسيناريوهات. "
            "يرجى طرح سؤال في أحد هذه المجالات."
        )
    return (
        "I’m optimized for AlphaLens investment workflows: portfolio analysis, policy checks, "
        "RAG over internal documents, market and news context, approvals, reports, and scenarios. "
        "Please ask about one of those areas."
    )
