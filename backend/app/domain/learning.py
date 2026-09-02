"""Learning engine — TRD § 10 / architecture-assessment.md § C.
Ported from ``automation/feedback.py`` unchanged in substance: same formula,
same floors/caps (0.7-1.4), same minimum-sample gating, same blend of
audience performance (70%) and Yahya's own approval rate (30%).

Protects against the brief's "learning must not collapse content strategy
into one topic" rule: MIN_SAMPLES gates any adjustment, and BOUNDS caps how
far a multiplier can move even with unlimited data.
"""

from __future__ import annotations

from collections import defaultdict

MIN_SAMPLES = 3          # minimum posts before a pillar's weight is touched
BOUNDS = (0.7, 1.4)       # multiplier floor/cap — learning adjusts priority, never kills a pillar
PERF_WEIGHT, APPROVAL_WEIGHT = 0.7, 0.3


def engagement_rate(metrics: dict) -> float:
    """Weighted engagement (TRD § 39) — comments/shares/saves count more than
    a bare like, follower growth counts most of all."""
    impressions = float(metrics.get("impressions") or metrics.get("views") or 0)
    if impressions <= 0:
        return 0.0
    weighted = (float(metrics.get("likes") or 0) + 2 * float(metrics.get("comments") or 0)
                + 3 * float(metrics.get("shares") or 0) + 2 * float(metrics.get("saves") or 0)
                + 1.5 * float(metrics.get("profile_visits") or 0)
                + 4 * float(metrics.get("followers_gained") or 0))
    return weighted / impressions


def performance_by_pillar(metric_rows: list[dict]) -> dict[str, float]:
    """`metric_rows`: [{pillar, impressions, likes, ...}, ...] — one row per
    measured post, already joined with its pillar."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in metric_rows:
        pillar = row.get("pillar")
        if pillar:
            buckets[pillar].append(engagement_rate(row))
    return {p: sum(v) / len(v) for p, v in buckets.items() if v}


def approval_by_pillar(decisions: list[dict]) -> dict[str, float]:
    """`decisions`: [{pillar, decision}, ...] — one row per approval decision
    (approved/edited count as approval; rejected does not)."""
    approved: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for row in decisions:
        pillar = row.get("pillar")
        if not pillar:
            continue
        total[pillar] += 1
        if row.get("decision") in ("approved", "edited"):
            approved[pillar] += 1
    return {p: approved[p] / n for p, n in total.items() if n >= MIN_SAMPLES}


def clamp(x: float) -> float:
    return round(max(BOUNDS[0], min(BOUNDS[1], x)), 3)


def compute_weights(metric_rows: list[dict], decisions: list[dict],
                    pillars: list[str]) -> tuple[dict[str, float], dict[str, dict]]:
    perf_means = performance_by_pillar(metric_rows)
    approvals = approval_by_pillar(decisions)
    counts: dict[str, int] = defaultdict(int)
    for row in metric_rows:
        if row.get("pillar"):
            counts[row["pillar"]] += 1

    global_perf = (sum(perf_means.values()) / len(perf_means)) if perf_means else 0.0
    global_appr = (sum(approvals.values()) / len(approvals)) if approvals else 0.0

    weights: dict[str, float] = {}
    detail: dict[str, dict] = {}
    for pillar in pillars:
        signal, parts = 1.0, []
        if counts[pillar] >= MIN_SAMPLES and global_perf > 0 and pillar in perf_means:
            ratio = perf_means[pillar] / global_perf
            signal += PERF_WEIGHT * (ratio - 1)
            parts.append(f"engagement {ratio:.2f}x average")
        if pillar in approvals and global_appr > 0:
            ratio = approvals[pillar] / global_appr
            signal += APPROVAL_WEIGHT * (ratio - 1)
            parts.append(f"{approvals[pillar]:.0%} approval rate")
        weights[pillar] = clamp(signal)
        detail[pillar] = {
            "multiplier": weights[pillar], "samples": counts[pillar],
            "engagement": round(perf_means.get(pillar, 0.0), 4),
            "why": ", ".join(parts) or "not enough data yet — neutral weight",
        }
    return weights, detail


def best_slots(metric_rows: list[dict], key: str, n: int = 3) -> list[tuple[float, str, int]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in metric_rows:
        if row.get(key):
            buckets[row[key]].append(engagement_rate(row))
    ranked = sorted(((sum(v) / len(v), k, len(v)) for k, v in buckets.items()), reverse=True)
    return ranked[:n]
