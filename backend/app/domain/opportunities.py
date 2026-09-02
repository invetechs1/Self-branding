"""Opportunity & Trend detection — architecture-assessment.md § E "Opportunity
Agent" / "Trend Agent" (rule-based first pass; ported from
``automation/persona.py::detect_opportunities``/``detect_trends``).

TRD § 45-46: a story isn't just content — it can be a potential Bassir feature,
partnership, investment thesis, or competitive signal.
"""

from __future__ import annotations

from .models import ClusterResult
from .text import hits

OPPORTUNITY_RULES = [
    ("bassir_feature", ["ai monitoring", "computer vision", "quantity takeoff", "ai estimation",
                        "erp", "copilot", "digital twin", "bim automation", "cash flow", "forecast"],
     "Potential feature inside Bassir"),
    ("partnership", ["partnership", "reseller", "integration", "distributor", "شراكة"],
     "Potential partnership or integration"),
    ("investment_theme", ["raises", "funding round", "series ", "valuation", "تمويل", "استثمار"],
     "Potential investment thesis"),
    ("competitive_intel", ["launches", "expands to saudi", "enters the middle east", "riyadh office",
                           "يفتتح", "يدخل السوق السعودي"],
     "Competitive intelligence — a player approaching the Saudi market"),
]


def detect_opportunities(cluster: ClusterResult) -> list[dict]:
    """Returns [{type, label}, ...] — zero or more per cluster."""
    text = cluster.primary.text
    return [{"type": kind, "label": label} for kind, terms, label in OPPORTUNITY_RULES
            if hits(text, terms)]


def detect_trends(clusters: list[ClusterResult], min_stories: int = 3) -> list[dict]:
    """A trend = several independent clusters pointing the same direction within
    the discovery window, grouped by pillar (cheap first pass; refined later by
    the Trend Agent's LLM narrative layer)."""
    buckets: dict[str, list[ClusterResult]] = {}
    for c in clusters:
        pillar = c.primary.meta.get("pillar", "ai_technology")
        buckets.setdefault(pillar, []).append(c)

    trends = []
    for pillar, group in buckets.items():
        if len(group) >= min_stories:
            trends.append({
                "pillar": pillar,
                "story_count": len(group),
                "avg_score": round(sum(c.primary.scores["total"] for c in group) / len(group), 1),
                "headline": f"Trend detected: acceleration in {pillar} — {len(group)} independent developments",
                "article_urls": [c.primary.url for c in group[:5]],
            })
    return sorted(trends, key=lambda t: -t["story_count"])
