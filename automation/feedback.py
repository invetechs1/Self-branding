#!/usr/bin/env python3
"""محرك التغذية الراجعة والتعلّم — الخطوتان 13-14 من سير العمل (§39، §40).

يقرأ:
  analytics/performance.csv   أداء المنشورات المنشورة (تُعبّأ يدوياً أو من تحليلات المنصات)
  automation/queue/queue.csv  ما اعتمده يحيى وما رفضه (إشارة تفضيل مباشرة)

ينتج:
  automation/learning/weights.yml   مضاعِفات لكل عمود محتوى، يقرؤها persona.score_story
  analytics/learning-report.md      ملخص بشري: ما ينجح، ما يُرفض، وأفضل أوقات النشر

المبدأ (§40): إن تفوّق تقاطع "الذكاء الاصطناعي + الإنشاءات" على أخبار الذكاء الاصطناعي العامة،
يرتفع وزنه تلقائياً في ترتيب الأخبار القادمة.

    python automation/feedback.py --learn        # تحديث الأوزان والتقرير
    python automation/feedback.py --show         # عرض الأوزان الحالية
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

from persona import load_persona

ROOT = Path(__file__).resolve().parent.parent
PERF = ROOT / "analytics" / "performance.csv"
QUEUE = ROOT / "automation" / "queue" / "queue.csv"
WEIGHTS = ROOT / "automation" / "learning" / "weights.yml"
REPORT = ROOT / "analytics" / "learning-report.md"

MIN_SAMPLES = 3          # أقل عدد منشورات قبل تعديل وزن عمود
BOUNDS = (0.7, 1.4)      # حدود المضاعِف — يمنع التعلّم من قتل التنوع
PERF_WEIGHT, APPROVAL_WEIGHT = 0.7, 0.3


def _f(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def engagement_rate(row: dict) -> float:
    """تفاعل مرجّح: التعليق والمشاركة والحفظ أثقل من الإعجاب (§39)."""
    impressions = _f(row.get("impressions")) or _f(row.get("views"))
    if impressions <= 0:
        return 0.0
    weighted = (_f(row.get("likes")) + 2 * _f(row.get("comments")) + 3 * _f(row.get("shares"))
                + 2 * _f(row.get("saves")) + 1.5 * _f(row.get("profile_visits"))
                + 4 * _f(row.get("followers_gained")))
    return weighted / impressions


def read_csv(path: Path) -> list:
    return list(csv.DictReader(path.open(encoding="utf-8"))) if path.exists() else []


def performance_by_pillar(perf: list) -> dict:
    buckets = defaultdict(list)
    for row in perf:
        pillar = row.get("pillar")
        if pillar:
            buckets[pillar].append(engagement_rate(row))
    return {p: sum(v) / len(v) for p, v in buckets.items() if v}


def approval_by_pillar(queue: list) -> dict:
    """نسبة ما اعتمده يحيى من كل عمود — تفضيله الشخصي المباشر."""
    approved, total = defaultdict(int), defaultdict(int)
    for row in queue:
        pillar, status = row.get("pillar"), row.get("status", "")
        if not pillar or status == "draft":
            continue
        total[pillar] += 1
        if status in ("approved", "posted", "manual"):
            approved[pillar] += 1
    return {p: approved[p] / n for p, n in total.items() if n >= MIN_SAMPLES}


def clamp(x: float) -> float:
    return round(max(BOUNDS[0], min(BOUNDS[1], x)), 3)


def compute_weights(perf: list, queue: list, persona: dict) -> tuple[dict, dict]:
    pillars = list(persona["content_pillars"])
    perf_means = performance_by_pillar(perf)
    approvals = approval_by_pillar(queue)
    counts = defaultdict(int)
    for row in perf:
        if row.get("pillar"):
            counts[row["pillar"]] += 1

    global_perf = (sum(perf_means.values()) / len(perf_means)) if perf_means else 0.0
    global_appr = (sum(approvals.values()) / len(approvals)) if approvals else 0.0

    weights, detail = {}, {}
    for pillar in pillars:
        signal, parts = 1.0, []
        if counts[pillar] >= MIN_SAMPLES and global_perf > 0 and pillar in perf_means:
            ratio = perf_means[pillar] / global_perf
            signal += PERF_WEIGHT * (ratio - 1)
            parts.append(f"أداء {ratio:.2f}×")
        if pillar in approvals and global_appr > 0:
            ratio = approvals[pillar] / global_appr
            signal += APPROVAL_WEIGHT * (ratio - 1)
            parts.append(f"اعتماد {approvals[pillar]:.0%}")
        weights[pillar] = clamp(signal)
        detail[pillar] = {"multiplier": weights[pillar], "samples": counts[pillar],
                          "engagement": round(perf_means.get(pillar, 0.0), 4),
                          "why": "، ".join(parts) or "بيانات غير كافية — وزن محايد"}
    return weights, detail


def best_slots(perf: list, key: str, n: int = 3) -> list:
    buckets = defaultdict(list)
    for row in perf:
        if row.get(key):
            buckets[row[key]].append(engagement_rate(row))
    ranked = sorted(((sum(v) / len(v), k, len(v)) for k, v in buckets.items()), reverse=True)
    return ranked[:n]


def learn(args) -> None:
    persona, perf, queue = load_persona(), read_csv(PERF), read_csv(QUEUE)
    if not perf and not queue:
        raise SystemExit("لا بيانات بعد — عبّئ analytics/performance.csv أو ولّد محتوى أولاً.")

    weights, detail = compute_weights(perf, queue, persona)
    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS.write_text(yaml.dump({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "samples": {"performance_rows": len(perf), "queue_rows": len(queue)},
        "pillar_multipliers": weights,
        "detail": detail,
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")

    ranked = sorted(detail.items(), key=lambda kv: -kv[1]["multiplier"])
    lines = [f"# تقرير التعلّم — {datetime.now():%Y-%m-%d}", "",
             f"مبني على {len(perf)} منشوراً مقيساً و{len(queue)} صفاً في الطابور.", "",
             "## أوزان الأعمدة بعد التعلّم", "",
             "| العمود | المضاعِف | عيّنات | متوسط التفاعل | السبب |", "|---|---|---|---|---|"]
    lines += [f"| {persona['content_pillars'][p]['label_ar']} | {d['multiplier']} | {d['samples']} "
              f"| {d['engagement']} | {d['why']} |" for p, d in ranked]
    for label, key in (("أفضل أوقات النشر", "time"), ("أفضل المنصات", "platform"),
                       ("أفضل اللغات", "language")):
        rows = best_slots(perf, key)
        lines += ["", f"## {label}", ""]
        lines += [f"- {k} — تفاعل {v:.4f} ({n} منشوراً)" for v, k, n in rows] or ["- بيانات غير كافية"]
    lines += ["", "---", "*وُلّد بواسطة `automation/feedback.py --learn`. "
              "الأوزان تدخل تلقائياً في ترتيب الأخبار عبر `persona.score_story`.*"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"الأوزان: {WEIGHTS.relative_to(ROOT)} | التقرير: {REPORT.relative_to(ROOT)}")
    for p, d in ranked:
        print(f"  {d['multiplier']:.2f}×  {p:26} {d['why']}")


def show(args) -> None:
    if not WEIGHTS.exists():
        raise SystemExit("لا أوزان بعد — شغّل: python automation/feedback.py --learn")
    print(WEIGHTS.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description="محرك التعلّم من الأداء والاعتماد")
    ap.add_argument("--learn", action="store_true", help="تحديث الأوزان وتوليد التقرير")
    ap.add_argument("--show", action="store_true", help="عرض الأوزان الحالية")
    args = ap.parse_args()
    if args.learn:
        learn(args)
    elif args.show:
        show(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
