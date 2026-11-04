"""Relevance scoring — architecture-assessment.md § E "Scoring Agent" (algorithmic, no LLM).

Ported from ``automation/persona.py::score_story`` and its component functions.
Formula matches ``docs/technical-requirements.md`` § 4 exactly:

    relevance = (w.personal_interest*personal_interest + w.business_relevance*business_relevance
                + w.saudi_gcc_relevance*saudi_gcc + w.strategic_importance*strategic_importance
                + w.audience_value*audience_value + w.freshness*freshness
                + w.source_credibility*source_credibility)
                * leadership_boost * learning_multiplier * saudi_first

Weights come from ``profile/persona.yml -> relevance_weights`` (currently Saudi/GCC 28 —
the heaviest component), never hardcoded. ``saudi_first`` is the post-weighting policy
from ``persona.yml -> saudi_first``: it boosts stories inside Yahya's six declared
activities, discounts global stories that carry no Saudi signal, and prefers Arabic
sources. Ported from ``automation/persona.py::score_story``.
"""

from __future__ import annotations

from datetime import datetime

from .models import Article, utcnow
from .text import hits, saturate

# Content pillars — keys MUST match profile/persona.yml -> content_pillars (they are stored in
# posts.pillar / raw_articles.pillar, foreign keys to pillars.key). Terms are the same
# Saudi-first keyword table the automation CLI uses (automation/persona.py); the
# regression test tests/test_pillar_alignment.py fails if the two ever drift apart.
PILLAR_TERMS = {
    "construction_projects": [
        "مقاولات", "مقاول", "مشروع إنشائي", "ترسية", "مناقصة", "منافسة", "مستخلص", "أمر تغييري",
        "مقاول الباطن", "البنية التحتية", "خرسانة", "سفلتة", "تشطيبات", "إدارة المشاريع",
        "هيئة المقاولين", "المشاريع الحكومية", "تأخر المشروع", "غرامة تأخير", "جدولة",
        "contractor", "construction", "tender", "infrastructure", "project management", "contech"],
    "ai_technology": [
        "ذكاء اصطناعي", "نموذج لغوي", "وكيل ذكي", "أتمتة", "تعلم آلي", "سدايا", "رؤية حاسوبية",
        "تحول رقمي", "برمجيات", "منصة رقمية", "مركز بيانات", "روبوت", "نظام ذكي",
        "artificial intelligence", "ai", "ai agent", "llm", "automation", "machine learning", "erp",
        "saas", "copilot", "computer vision", "data center", "digital twin", "bim"],
    "government_decisions": [
        "وزارة الموارد البشرية", "التأمينات الاجتماعية", "وزارة التجارة", "الزكاة والضريبة",
        "الفاتورة الإلكترونية", "نطاقات", "السعودة", "التوطين", "مكتب العمل", "قوى", "مساند",
        "نظام العمل", "لائحة", "قرار وزاري", "تعميم", "مجلس الوزراء", "وزارة البلديات",
        "المحتوى المحلي", "اعتماد", "نظام المنافسات", "إلزام", "اشتراط", "اعتباراً من",
        "regulation", "ministerial", "mandate", "compliance"],
    "site_quality": [
        "عامل بناء", "العمالة", "سلامة الموقع", "إصابات العمل", "السلامة المهنية", "أخطاء التنفيذ",
        "عيوب البناء", "تشققات", "العزل", "كود البناء", "جودة التنفيذ", "الإشراف الهندسي",
        "مخالفات البناء", "رخصة بناء", "الأمانة", "بلدي", "سقالات", "شهادة إشغال", "انهيار",
        "building defect", "site safety", "worker safety", "building code", "inspection"],
    "saudi_economy": [
        "الاقتصاد السعودي", "رؤية 2030", "صندوق الاستثمارات", "الرياض", "نيوم", "المشاريع الكبرى",
        "الناتج المحلي", "القطاع الخاص", "الاستثمار الأجنبي", "تداول", "طرح عام", "نمو",
        "saudi economy", "vision 2030", "pif", "giga-project", "gdp", "non-oil"],
    "saudi_trends": [
        "ترند", "الأكثر تداولاً", "يتصدر", "وسم", "هاشتاق", "الأكثر بحثاً", "جدل", "تفاعل",
        "حديث السوشيال", "trending", "viral"],
    "real_estate": [
        "عقار", "تطوير عقاري", "إسكان", "سكني", "تمويل عقاري", "أسعار الأراضي", "صندوق عقاري",
        "الطلب على المساكن", "سكني", "ريت", "real estate", "proptech", "housing", "mortgage", "reit"],
    "occasions": [
        "اليوم الوطني", "يوم التأسيس", "يوم العلم", "إجازة رسمية", "عيد الفطر", "عيد الأضحى",
        "رمضان", "موسم الرياض", "اليوم العالمي", "الاحتفال", "national day", "founding day"],
    "business_leadership": [
        "إدارة", "قيادة", "التوظيف", "الإنتاجية", "ثقافة العمل", "ريادة أعمال", "شركة ناشئة",
        "تمويل", "استثمار", "استحواذ", "leadership", "management", "startup", "funding", "hiring"],
}

_PILLAR_ALIAS = {"AI": "ai_technology", "Construction": "construction_projects", "Business": "business_leadership",
        "Real Estate": "real_estate", "Technology": "ai_technology", "Project Management": "construction_projects",
        "Saudi Arabia": "saudi_economy", "Entrepreneurship": "business_leadership", "ERP": "ai_technology",
        "AI Agents": "ai_technology", "Business Automation": "ai_technology",
        "Traditional Industries": "construction_projects"}


def activity_hits(article: Article, persona: dict) -> list:
    """Which of the six declared Saudi activities the article falls into
    (persona.yml -> saudi_activities). Ordered by match strength x activity weight,
    so the dominant topic — not config order — decides the pillar and the angle."""
    out = []
    for key, spec in (persona.get("saudi_activities") or {}).items():
        found = hits(article.text, spec.get("keywords", []))
        if found:
            out.append({"key": key, "label": spec.get("label_ar", key),
                        "pillar": spec.get("pillar", "saudi_economy"),
                        "weight": float(spec.get("weight", 1.0)), "hits": len(found)})
    return sorted(out, key=lambda a: -a["hits"] * a["weight"])


def is_arabic(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if "\u0600" <= c <= "\u06ff") / len(letters) > 0.4


def _interest_hits(text: str, terms, persona: dict) -> list:
    aliases = persona.get("interest_aliases", {})
    return [term for term in terms if hits(text, [term] + list(aliases.get(term, [])))]


def personal_interest_score(article: Article, persona: dict) -> tuple[float, list]:
    graph, tw = persona["interest_graph"], persona["interest_graph"]["tier_weights"]
    total, matched = 0.0, []
    for tier, weight in (("tier_1", tw["tier_1"]), ("tier_2", tw["tier_2"]), ("tier_3", tw["tier_3"])):
        found = _interest_hits(article.text, graph[tier], persona)
        matched += found
        total += weight * saturate(len(found), 3)

    # A declared activity is an explicit interest: a ministry decision aimed at
    # contractors must not score zero just because it is written in Arabic and
    # never spells out an interest-graph term.
    acts = activity_hits(article, persona)
    if acts:
        best = max(a["weight"] * saturate(a["hits"], 2) for a in acts)
        total = max(total, min(1.0, best + 0.15 * (len(acts) - 1)))
        matched += [a["label"] for a in acts]
    return min(1.0, total), matched


def business_relevance_score(article: Article, persona: dict) -> tuple[float, list]:
    matched, best = [], 0.0
    for domain, spec in persona["business_domains"].items():
        found = hits(article.text, spec.get("keywords", []))
        if found:
            matched.append(domain)
            best = max(best, saturate(len(found), 2))
    return min(1.0, best + 0.15 * max(0, len(matched) - 1)), matched


def saudi_gcc_score(article: Article, persona: dict) -> tuple[float, str]:
    geo, best_region, best = persona["geography"], "global", 0.0
    for region, terms in geo["terms"].items():
        if hits(article.text, terms):
            w = geo["priority"].get(region, 0.4)
            if w > best:
                best, best_region = w, region
    # A Saudi government body named in the text is conclusive evidence of a Saudi story.
    # saudi_watchlist is deliberately NOT used here: it lists topics ("Infrastructure",
    # "Tourism", "Logistics"), not places, so any global story matching one of those words
    # used to be scored as Saudi — which silently defeated the Saudi-first policy.
    if hits(article.text, persona.get("government_watchlist", [])):
        best = max(best, geo["priority"]["saudi_arabia"])
        best_region = "saudi_arabia"

    # Nothing in the text? The source settles it: a Saudi ministry's own news page is
    # Saudi even when the headline never says so.
    if not best:
        hinted = article.meta.get("feed_region")
        if hinted in geo["priority"]:
            return geo["priority"][hinted], hinted
    return best or geo["priority"]["global"], best_region


def strategic_score(article: Article, persona: dict) -> float:
    sig = persona["strategic_signals"]
    high, medium = len(hits(article.text, sig["high"])), len(hits(article.text, sig["medium"]))
    return min(1.0, 0.6 * saturate(high, 2) + 0.4 * saturate(medium, 2) + (0.4 if high else 0.0))


def audience_value_score(article: Article, persona: dict) -> float:
    return saturate(len(hits(article.text, persona["audience_value_signals"])), 2)


def freshness_score(article: Article, persona: dict, now: datetime) -> float:
    if not article.published:
        return 0.5
    th = persona["thresholds"]
    age_h = max(0.0, (now - article.published).total_seconds() / 3600)
    if age_h > th["freshness_max_age_hours"]:
        return 0.0
    return 0.5 ** (age_h / th["freshness_half_life_hours"])


def credibility_score(article: Article, persona: dict) -> float:
    return persona["source_credibility"].get(article.source_type, 20) / 100


def pillars_ranked(article: Article) -> list:
    # ties break by declaration order (the persona's priority order), not alphabetically
    ranked = sorted(((len(hits(article.text, terms)), -i, p) for i, (p, terms) in enumerate(PILLAR_TERMS.items())),
                    reverse=True)
    return [p for n, _, p in ranked if n] or ["ai_technology"]


def pillar_of(article: Article, persona: dict) -> str:
    return pillars_ranked(article)[0]


def leadership_boost(article: Article, persona: dict) -> tuple[float, str]:
    """TRD § 44: thought-leadership intersections get a relevance boost."""
    graph = persona["thought_leadership_graph"]
    candidates = [graph["primary"]] + list(graph["secondary"])
    for c in candidates:
        if all(hits(article.text, [term]) or hits(article.text, PILLAR_TERMS.get(_PILLAR_ALIAS.get(term, ""), []))
               for term in c["intersection"]):
            return c["boost"], " × ".join(c["intersection"])
    return 1.0, ""


def score_article(article: Article, persona: dict, now: datetime | None = None,
                   learning: dict | None = None) -> Article:
    """Computes the 0-100 relevance score and stores it on article.scores (TRD § 4)."""
    now = now or utcnow()
    learning = learning or {}
    w = persona["relevance_weights"]

    interest, interest_hits = personal_interest_score(article, persona)
    business, domains = business_relevance_score(article, persona)
    geo, region = saudi_gcc_score(article, persona)
    strategic = strategic_score(article, persona)
    audience = audience_value_score(article, persona)
    fresh = freshness_score(article, persona, now)
    cred = credibility_score(article, persona)

    base = (w["personal_interest"] * interest + w["business_relevance"] * business
            + w["saudi_gcc_relevance"] * geo + w["strategic_importance"] * strategic
            + w["audience_value"] * audience + w["freshness"] * fresh
            + w["source_credibility"] * cred)

    activities = activity_hits(article, persona)
    pillar = activities[0]["pillar"] if activities else pillar_of(article, persona)
    # An announcement from a government body is a government-decisions story first,
    # however many contracting words the headline also contains.
    if article.meta.get("gov_entity") or (
            hits(article.text, persona.get("government_watchlist", []))
            and any(a["key"] == "government_decisions" for a in activities)):
        pillar = "government_decisions"

    boost, intersection = leadership_boost(article, persona)
    multiplier = boost * float(learning.get(pillar, 1.0))

    # Saudi-first policy (persona.yml -> saudi_first): applied after the weighted base,
    # so global noise cannot outrank a Saudi story that matters to Yahya's audience.
    sf = persona.get("saudi_first") or {}
    saudi_note = ""
    if sf.get("enabled", True):
        if activities:
            multiplier *= float(sf.get("activity_match_boost", 1.15))
        if geo <= persona["geography"]["priority"]["global"]:
            ai_only = bool(activities) and all(a["key"] == "artificial_intelligence" for a in activities)
            if ai_only:
                factor = float(sf.get("global_ai_exemption", 0.8))
                saudi_note = "ذكاء اصطناعي عالمي — يحتاج ربطاً سعودياً"
            elif activities:
                factor = float(sf.get("activity_no_saudi_multiplier", 0.75))
                saudi_note = "مرجع عالمي داخل أنشطتك — اربطه بالسوق السعودي"
            else:
                factor = float(sf.get("no_saudi_signal_multiplier", 0.45))
                saudi_note = "بلا إشارة سعودية ولا نشاط من أنشطتك"
            multiplier *= factor
        if is_arabic(article.title):
            multiplier *= float(sf.get("arabic_source_boost", 1.08))

    total = round(min(100.0, base * multiplier), 1)

    article.scores = {"total": total, "base": round(base, 1), "personal_interest": round(interest, 2),
                      "business_relevance": round(business, 2), "saudi_gcc": round(geo, 2),
                      "strategic": round(strategic, 2), "audience_value": round(audience, 2),
                      "freshness": round(fresh, 2), "credibility": round(cred, 2),
                      "multiplier": round(multiplier, 2)}
    article.meta.update({"pillar": pillar, "pillars": pillars_ranked(article)[:3],
                         "activities": [a["label"] for a in activities],
                         "activity_keys": [a["key"] for a in activities],
                         "saudi_note": saudi_note, "arabic": is_arabic(article.title),
                         "region": region, "domains": domains,
                         "interest_hits": interest_hits[:8], "intersection": intersection})
    return article
