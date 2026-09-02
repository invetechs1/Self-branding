"""Relevance scoring — architecture-assessment.md § E "Scoring Agent" (algorithmic, no LLM).

Ported from ``automation/persona.py::score_story`` and its component functions.
Formula matches ``docs/technical-requirements.md`` § 4 exactly:

    relevance = (25*personal_interest + 20*business_relevance + 15*saudi_gcc
                + 15*strategic_importance + 10*audience_value + 10*freshness
                + 5*source_credibility) * leadership_boost * learning_multiplier
"""

from __future__ import annotations

from datetime import datetime

from .models import Article, utcnow
from .text import hits, saturate

PILLAR_TERMS = {
    "ai_technology": ["artificial intelligence", "ai ", " ai", "ai agent", "enterprise ai", "llm",
                      "machine learning", "automation", "erp", "saas", "copilot", "software",
                      "data center", "cloud", "ذكاء اصطناعي", "أتمتة", "برمجيات", "نموذج لغوي"],
    "construction_engineering": ["construction", "contech", "bim", "digital twin", "engineering",
                                 "contractor", "concrete", "asphalt", "infrastructure", "project management",
                                 "reality capture", "laser scanning", "drone", "quantity takeoff",
                                 "إنشاءات", "مقاولات", "هندسة", "خرسانة", "بنية تحتية", "إدارة مشاريع"],
    "real_estate": ["real estate", "proptech", "housing", "residential", "reit", "mortgage", "land price",
                    "عقار", "إسكان", "تطوير عقاري", "تمويل عقاري"],
    "saudi_economy": ["saudi", "vision 2030", "pif", "riyadh", "neom", "public investment fund",
                      "السعودية", "رؤية 2030", "الرياض", "صندوق الاستثمارات"],
    "entrepreneurship": ["startup", "founder", "entrepreneur", "bootstrapped", "product-market",
                         "ريادة أعمال", "مؤسس", "شركة ناشئة"],
    "investment": ["funding", "raises", "series ", "venture capital", "private equity", "ipo",
                   "valuation", "acquisition", "استثمار", "تمويل", "استحواذ", "طرح"],
    "business_management": ["management", "productivity", "business intelligence", "operations",
                            "workforce", "logistics", "fleet", "supply chain",
                            "إدارة", "إنتاجية", "تشغيل", "لوجستي", "أسطول"],
    "leadership_lessons": ["leadership", "culture", "hiring", "lesson", "قيادة", "ثقافة", "توظيف", "درس"],
}

_PILLAR_ALIAS = {
    "AI": "ai_technology", "Construction": "construction_engineering", "Business": "business_management",
    "Real Estate": "real_estate", "Technology": "ai_technology", "Project Management": "construction_engineering",
    "Saudi Arabia": "saudi_economy", "Entrepreneurship": "entrepreneurship", "ERP": "ai_technology",
    "AI Agents": "ai_technology", "Business Automation": "ai_technology",
    "Traditional Industries": "construction_engineering",
}


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
    if hits(article.text, persona["saudi_watchlist"]):
        best = max(best, geo["priority"]["saudi_arabia"])
        best_region = "saudi_arabia"
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
    ranked = sorted(((len(hits(article.text, terms)), p) for p, terms in PILLAR_TERMS.items()),
                    reverse=True)
    return [p for n, p in ranked if n] or ["ai_technology"]


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

    pillar = pillar_of(article, persona)
    boost, intersection = leadership_boost(article, persona)
    multiplier = boost * float(learning.get(pillar, 1.0))
    total = round(min(100.0, base * multiplier), 1)

    article.scores = {"total": total, "base": round(base, 1), "personal_interest": round(interest, 2),
                      "business_relevance": round(business, 2), "saudi_gcc": round(geo, 2),
                      "strategic": round(strategic, 2), "audience_value": round(audience, 2),
                      "freshness": round(fresh, 2), "credibility": round(cred, 2),
                      "multiplier": round(multiplier, 2)}
    article.meta.update({"pillar": pillar, "pillars": pillars_ranked(article)[:3],
                         "region": region, "domains": domains,
                         "interest_hits": interest_hits[:8], "intersection": intersection})
    return article
