"""Intent-specific app help copy (avoid one generic reply for every capability question)."""

from __future__ import annotations

import re


def compose_app_help_reply(user_text: str, response_language: str) -> str:
    """Return a tailored answer for the user's app-help question."""
    text = (user_text or "").strip()
    lowered = text.lower()
    lang = (response_language or "en").lower().split("-", 1)[0]

    if re.search(r"français|francais|en\s+français|comprends.*français|comprends.*francais", lowered):
        return _t(
            lang,
            en=(
                "Yes — when you write in French, I can respond in French. "
                "I also support English, German, and Arabic, depending on your provider configuration."
            ),
            fr=(
                "Oui — lorsque vous écrivez en français, je peux répondre en français. "
                "Je prends aussi en charge l’anglais, l’allemand et l’arabe selon la configuration des fournisseurs."
            ),
            de=(
                "Ja — wenn Sie auf Französisch schreiben, kann ich auf Französisch antworten. "
                "Außerdem unterstütze ich je nach Konfiguration Englisch, Deutsch und Arabisch."
            ),
            ar=(
                "نعم — عندما تكتب بالفرنسية يمكنني الرد بالفرنسية. "
                "أدعم أيضًا الإنجليزية والألمانية والعربية حسب إعدادات المزوّد."
            ),
        )

    if _is_languages_question(lowered):
        return _t(
            lang,
            en=(
                "I support English, German, French, and Arabic for multilingual responses and speech, "
                "depending on your provider configuration (OpenAI for transcription and chat)."
            ),
            fr=(
                "Je prends en charge l’anglais, l’allemand, le français et l’arabe pour les réponses multilingues "
                "et la parole, selon la configuration de vos fournisseurs (p. ex. OpenAI)."
            ),
            de=(
                "Ich unterstütze Englisch, Deutsch, Französisch und Arabisch für mehrsprachige Antworten "
                "und Spracheingabe — abhängig von Ihrer Provider-Konfiguration (z. B. OpenAI)."
            ),
            ar=(
                "أدعم الإنجليزية والألمانية والفرنسية والعربية للردود متعددة اللغات وللتحدث، "
                "حسب إعدادات المزوّد (مثل OpenAI)."
            ),
        )

    if _is_approvals_workflow_question(lowered):
        return _t(
            lang,
            en=(
                "Approvals are the human-in-the-loop checkpoint. When the agent recommends a sensitive action "
                "such as trim, rebalance, buy, sell, or escalation, it can create an approval request. "
                "A reviewer can approve, reject, or ask for more analysis. Status is persisted and visible "
                "on the Approvals page and dashboard."
            ),
            fr=(
                "Les validations sont le point de contrôle humain. Lorsque l’agent recommande une action sensible "
                "(réduction, rééquilibrage, achat, vente, escalade), une demande de validation peut être créée. "
                "Un relecteur peut approuver, refuser ou demander plus d’analyse. Le statut est conservé "
                "et visible sur la page Validations et le tableau de bord."
            ),
            de=(
                "Freigaben sind der Human-in-the-Loop-Schritt. Empfiehlt der Agent eine sensible Aktion "
                "(Trimmen, Rebalancing, Kauf, Verkauf, Eskalation), kann eine Freigabe angelegt werden. "
                "Prüfer können zustimmen, ablehnen oder mehr Analyse anfordern. Der Status wird gespeichert "
                "und unter Freigaben sowie im Dashboard angezeigt."
            ),
            ar=(
                "الموافقات هي نقطة المراجعة البشرية. عندما يوصي الوكيل بإجراء حساس مثل التخفيض أو إعادة التوازن "
                "أو الشراء أو البيع أو التصعيد، يمكن إنشاء طلب موافقة. يمكن للمراجع الموافقة أو الرفض أو طلب المزيد من التحليل. "
                "تُحفظ الحالة وتظهر في صفحة الموافقات ولوحة المعلومات."
            ),
        )

    if _is_tools_question(lowered):
        return _t(
            lang,
            en=(
                "I can use portfolio analysis, policy and risk checks, RAG over internal documents, market data, "
                "web and news search, macro data, SEC filings, and workflows for reports, scenarios, approvals, "
                "feedback, and usage tracking — depending on what’s configured in your environment."
            ),
            fr=(
                "Je peux utiliser l’analyse de portefeuille, les contrôles de politique et de risque, le RAG sur documents internes, "
                "les données de marché, la recherche web/actualités, la macro, les dépôts SEC, ainsi que rapports, scénarios, "
                "validations, retours et suivi d’usage — selon votre configuration."
            ),
            de=(
                "Ich kann Portfolioanalyse, Policy- und Risiko-Checks, RAG über interne Dokumente, Marktdaten, Web/News, "
                "Makro, SEC-Filings sowie Reports, Szenarien, Freigaben, Feedback und Nutzungs-Tracking nutzen — je nach Konfiguration."
            ),
            ar=(
                "يمكنني استخدام تحليل المحفظة، وفحص السياسة والمخاطر، وRAG على المستندات الداخلية، وبيانات السوق، "
                "والبحث في الويب والأخبار، والبيانات الكلية، وملفات SEC، ومسارات التقارير والسيناريوهات والموافقات والملاحظات وتتبع الاستخدام — حسب الإعدادات."
            ),
        )

    if _is_rag_explainer_question(lowered):
        return _t(
            lang,
            en=(
                "Internal documents are chunked, embedded, stored in Qdrant, retrieved when your question matches them, "
                "and surfaced as cited sources on investment answers when RAG runs."
            ),
            fr=(
                "Les documents internes sont découpés en segments, vectorisés, stockés dans Qdrant, récupérés lorsque votre question correspond, "
                "puis cités dans les réponses d’investissement lorsque le RAG est utilisé."
            ),
            de=(
                "Interne Dokumente werden in Chunks zerlegt, eingebettet, in Qdrant gespeichert, bei passenden Fragen abgerufen "
                "und in Investment-Antworten als Quellen angezeigt, wenn RAG läuft."
            ),
            ar=(
                "تُقسَّم المستندات الداخلية إلى مقاطع، وتُضمَّن في متجهات، وتُخزَّن في Qdrant، وتُسترجع عندما تناسب سؤالك، "
                "وتُعرض كمصادر في إجابات الاستثمار عند تشغيل RAG."
            ),
        )

    if _is_upload_question(lowered):
        return _t(
            lang,
            en=(
                "Use the Knowledge Base or upload flows in the app to add documents; they’re ingested into the vector store "
                "for RAG retrieval on later investment questions."
            ),
            fr=(
                "Utilisez la base de connaissances ou les parcours d’import dans l’application ; les documents sont ingérés "
                "dans le magasin vectoriel pour le RAG sur les questions d’investissement ultérieures."
            ),
            de=(
                "Nutzen Sie die Knowledge Base oder Upload-Flows in der App; Dokumente werden in den Vektorspeicher aufgenommen "
                "und später per RAG abgefragt."
            ),
            ar=(
                "استخدم قاعدة المعرفة أو مسارات الرفع في التطبيق؛ تُدمَج الملفات في المخزن المتجهي لاسترجاع RAG لاحقًا."
            ),
        )

    if _is_reports_or_scenarios_question(lowered):
        return _t(
            lang,
            en=(
                "Reports and scenarios are first-class workflows: you can generate structured outputs from chat context "
                "and run what-if analyses from the dedicated pages, with results you can revisit later."
            ),
            fr=(
                "Rapports et scénarios sont des parcours dédiés : vous pouvez produire des livrables structurés depuis le chat "
                "et lancer des analyses de scénarios depuis leurs pages, avec un historique consultable."
            ),
            de=(
                "Reports und Szenarien sind eigene Workflows: strukturierte Ausgaben aus dem Chat und Was-wäre-wenn-Analysen "
                "über die jeweiligen Seiten, mit nachverfolgbaren Ergebnissen."
            ),
            ar=(
                "التقارير والسيناريوهات مسارات كاملة: يمكنك إنشاء مخرجات منظمة من المحادثة وتشغيل تحليلات افتراضية من صفحاتها مع إمكانية المراجعة لاحقًا."
            ),
        )

    if _is_data_question(lowered):
        return _t(
            lang,
            en=(
                "I use your configured portfolio and policy snapshots, optional live market and news providers, "
                "macro feeds, SEC sources when enabled, and your internal knowledge base via RAG — plus synthetic fallbacks in dev."
            ),
            fr=(
                "J’utilise vos instantanés de portefeuille et de politique, les fournisseurs marché/actualités et macro configurés, "
                "les sources SEC si activées, et votre base documentaire via RAG — avec repli synthétique en développement."
            ),
            de=(
                "Ich nutze konfigurierte Portfolio- und Policy-Snapshots, optional Markt-/News- und Makro-Provider, SEC wenn aktiv, "
                "und interne Dokumente per RAG — in Dev ggf. synthetische Fallbacks."
            ),
            ar=(
                "أستخدم لقطات المحفظة والسياسة، ومزوّدي السوق والأخبار والكلي عند التفعيل، ومصادر SEC عند توفرها، "
                "وقاعدة المعرفة عبر RAG — مع بدائل تركيبية في بيئة التطوير."
            ),
        )

    if _is_limitations_question(lowered):
        return _t(
            lang,
            en=(
                "I’m not a substitute for professional investment, legal, or tax advice. Outputs depend on data quality "
                "and provider connectivity; always verify material decisions with your team and policies."
            ),
            fr=(
                "Je ne remplace pas un conseil professionnel en investissement, droit ou fiscal. Les résultats dépendent "
                "de la qualité des données et des connexions aux fournisseurs ; validez les décisions avec votre équipe."
            ),
            de=(
                "Ich ersetze keine professionelle Anlage-, Rechts- oder Steuerberatung. Ergebnisse hängen von Datenqualität "
                "und Provider-Anbindung ab; wichtige Entscheidungen mit Team und Policies abstimmen."
            ),
            ar=(
                "لست بديلاً عن استشارة استثمارية أو قانونية أو ضريبية مهنية. تعتمد النتائج على جودة البيانات واتصال المزوّدين؛ "
                "راجع القرارات المهمة مع فريقك وسياساتك."
            ),
        )

    # Default: concise capability summary (distinct from the old “languages only” blob).
    return _t(
        lang,
        en=(
            "I’m AlphaLens: I help with portfolio and risk analysis, policy checks, RAG over internal documents, "
            "market and news context, and workflows like approvals, reports, and scenarios. What would you like to do?"
        ),
        fr=(
            "Je suis AlphaLens : analyse de portefeuille et des risques, contrôles de politique, RAG sur documents internes, "
            "contexte marché et actualité, et workflows comme validations, rapports et scénarios. Que souhaitez-vous faire ?"
        ),
        de=(
            "Ich bin AlphaLens: Portfolio- und Risikoanalyse, Policy-Checks, RAG über interne Dokumente, Markt-/News-Kontext "
            "sowie Workflows wie Freigaben, Reports und Szenarien. Was möchten Sie tun?"
        ),
        ar=(
            "أنا AlphaLens: أدعم تحليل المحفظة والمخاطر، وفحص السياسات، وRAG على المستندات الداخلية، وسياق السوق والأخبار، "
            "ومسارات مثل الموافقات والتقارير والسيناريوهات. ماذا تريد أن تفعل؟"
        ),
    )


def _t(lang: str, *, en: str, fr: str, de: str, ar: str) -> str:
    if lang == "fr":
        return fr
    if lang == "de":
        return de
    if lang == "ar":
        return ar
    return en


def _is_languages_question(lowered: str) -> bool:
    return bool(
        re.search(
            r"\b(how\s+many\s+languages|languages?\s+do\s+you|supported\s+languages|multilingual|"
            r"speech|voice).*\b(support|work|available)|\b(speak|understand)\s+(english|french|german|arabic|deutsch|français)",
            lowered,
        )
    )


def _is_approvals_workflow_question(lowered: str) -> bool:
    return bool(
        re.search(
            r"\b(how\s+do\s+approvals\s+work|how\s+approvals\s+work|approval\s+workflow|what\s+are\s+approvals|"
            r"explain\s+approvals|approvals\s+in\s+alphalens)\b",
            lowered,
        )
    )


def _is_tools_question(lowered: str) -> bool:
    return bool(
        re.search(
            r"\b(what\s+tools|which\s+tools|tools\s+do\s+you|capabilities|what\s+can\s+you\s+do)\b",
            lowered,
        )
    )


def _is_rag_explainer_question(lowered: str) -> bool:
    return bool(
        re.search(
            r"\b(how\s+does\s+rag\s+work|explain\s+rag|what\s+is\s+rag|rag\s+here)\b",
            lowered,
        )
    )


def _is_upload_question(lowered: str) -> bool:
    return bool(re.search(r"\b(upload|how\s+do\s+i\s+upload|add\s+documents?)\b", lowered))


def _is_reports_or_scenarios_question(lowered: str) -> bool:
    return bool(
        re.search(
            r"\b(how\s+do\s+reports\s+work|how\s+reports\s+work|how\s+do\s+scenarios\s+work|scenarios\s+work)\b",
            lowered,
        )
    )


def _is_data_question(lowered: str) -> bool:
    return bool(re.search(r"\bwhat\s+data\s+do\s+you\s+use\b", lowered))


def _is_limitations_question(lowered: str) -> bool:
    return bool(re.search(r"\b(limitations?|what\s+can'?t\s+you|what\s+are\s+your\s+limits)\b", lowered))
