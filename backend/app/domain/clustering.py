"""Duplicate detection & fact confidence — architecture-assessment.md § E "Clustering" +
"Verify" agents (deterministic halves).

Ported from ``automation/persona.py::cluster_stories`` / ``fact_confidence``. This is the
lexical pre-filter (Jaccard + overlap on headline tokens); pgvector cosine similarity is
added on top of this, not instead of it, once ``raw_articles.embedding`` is populated
(architecture-assessment.md § C — "keep the lexical pre-filter as a floor").

CRITICAL RULE (brief § 15): one real-world event = one story cluster = at most one
content opportunity. Multiple outlets reporting the same event must merge into a single
cluster, never spawn separate posts.
"""

from __future__ import annotations

import re

from .models import Article, ClusterResult
from .scoring import credibility_score
from .text import similarity, tokens

NUMBER_RE = re.compile(r"\d[\d,.]*\s?(?:%|billion|million|مليار|مليون)?")


def cluster_articles(articles: list[Article], persona: dict) -> list[ClusterResult]:
    """Groups multiple reports of the same event into one cluster (TRD § 21)."""
    threshold = persona["thresholds"]["duplicate_similarity"]
    raw_clusters: list[dict] = []
    for article in sorted(articles, key=lambda a: -a.scores.get("total", 0)):
        for cluster in raw_clusters:
            if (similarity(article.title, cluster["primary"].title) >= threshold
                    and len(tokens(article.title) & tokens(cluster["primary"].title)) >= 3):
                cluster["supporting"].append(article)
                break
        else:
            raw_clusters.append({"primary": article, "supporting": []})

    results = []
    for c in raw_clusters:
        members = [c["primary"]] + c["supporting"]
        best_source = max(members, key=lambda a: credibility_score(a, persona))
        results.append(ClusterResult(
            primary=c["primary"],
            supporting=c["supporting"],
            best_source=best_source,
            source_count=len(members),
            fact_confidence=_fact_confidence(c["primary"], c["supporting"], best_source, persona),
        ))
    return results


def _fact_confidence(primary: Article, supporting: list[Article], best_source: Article,
                      persona: dict) -> float:
    """TRD § 22: fact confidence = best-source credibility + independent-source corroboration
    - conflicting numbers penalty."""
    members = [primary] + supporting
    best = credibility_score(best_source, persona)
    corroboration = min(0.2, 0.1 * (len({m.source for m in members}) - 1))
    numbers = [set(NUMBER_RE.findall(m.text)) for m in members if NUMBER_RE.search(m.text)]
    conflict = 0.0
    if len(numbers) > 1:
        shared = set.intersection(*numbers)
        conflict = 0.0 if shared else 0.15
    return round(max(0.0, min(1.0, 0.85 * best + corroboration - conflict)), 2)


def is_repeat(text: str, previous: list[str], threshold: float = 0.62) -> bool:
    """TRD § 43: prevents re-publishing the same argument/hook as a prior post."""
    return any(similarity(text[:400], prev[:400]) >= threshold for prev in previous)
