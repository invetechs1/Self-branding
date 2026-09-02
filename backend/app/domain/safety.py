"""Safety Agent (deterministic gate) — architecture-assessment.md § E.

Ported from ``automation/persona.py::classify_approval`` /
``violates_personal_experience_rule``. This is the hard gate the brief's rule 16
demands: an LLM may add flags, but only this deterministic logic decides the final
green/yellow/red level, and RED can never auto-publish (brief rule "RED CONTENT
MUST NEVER AUTO-PUBLISH" / TRD § 6).
"""

from __future__ import annotations

from .text import hits, normalize, tokens

FIRST_PERSON_CLAIM = ["في شركتي", "طبقنا", "نفذنا في", "عملائي", "i implemented", "in my company",
                      "we deployed", "my client"]


def classify_approval(text: str, persona: dict, fact_conf: float = 1.0) -> tuple[str, list]:
    """Returns (green|yellow|red, reasons). Red must never auto-publish."""
    safety, t = persona["safety"], normalize(text)
    reasons = []

    red = hits(t, safety["red_flag_terms"])
    if red:
        reasons.append(f"sensitive terms: {', '.join(map(str, red[:4]))}")
    claims = hits(t, FIRST_PERSON_CLAIM)
    if claims:
        reasons.append("first-person experience claim needs verification against facts.yml")
    th = persona["thresholds"]
    if fact_conf < th["fact_confidence_red"]:
        reasons.append(f"low fact confidence ({fact_conf}) — single weak source or conflicting numbers")
    if reasons:
        return "red", reasons

    yellow = hits(t, safety["yellow_flag_terms"])
    if yellow:
        reasons.append(f"opinion or prediction: {', '.join(map(str, yellow[:4]))}")
    if fact_conf < th["fact_confidence_autopublish"]:
        reasons.append(f"fact confidence below auto-publish threshold ({fact_conf}) — verify source")
    return ("yellow", reasons) if reasons else ("green", [])


def violates_personal_experience_rule(text: str, facts: dict) -> bool:
    """Brief rule 2 / TRD § 34: an unattributed first-person experience claim."""
    t = normalize(text)
    if not hits(t, FIRST_PERSON_CLAIM):
        return False
    ventures = [v.get("name", "") for v in facts.get("ventures", {}).get("items", [])]
    return not any(normalize(v) in t for v in ventures if v)


def mix_deficit(published_counts: dict, persona: dict) -> list:
    """Ranks pillars by distance below their target share — used to bias generation order."""
    pillars, total = persona["content_pillars"], max(1, sum(published_counts.values()))
    gaps = []
    for name, spec in pillars.items():
        actual = published_counts.get(name, 0) / total
        gaps.append((round(spec["share"] - actual, 3), name))
    return [name for gap, name in sorted(gaps, reverse=True)]
