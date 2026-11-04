#!/usr/bin/env python3
"""ربط الفرص الواردة بالمحتوى الذي أنتجها — قياس الهدف لا الضجيج.

الهدف المعلن ليس عدد المتابعين بل: سمعة ← سلطة ← شبكة ← فرص أعمال.
هذا الملف يقيس الأخير: أي عمود محتوى، وأي منصة، وأي نوع منشور جلب فرصاً فعلية.

    python automation/attribution.py --log --channel linkedin --kind طلب_عرض --post 501
    python automation/attribution.py --update 7 --stage فوز
    python automation/attribution.py --report
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persona import load_persona, rel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "outreach" / "inbound-log.csv"
QUEUE = ROOT / "automation" / "queue" / "queue.csv"
REPORT = ROOT / "analytics" / "attribution-report.md"

FIELDS = ["id", "date", "channel", "kind", "label", "source_post", "stage", "weight", "notes"]
CHANNELS = ("linkedin", "x", "whatsapp", "call", "email", "referral", "event", "other")
STAGES = ("جديد", "تواصل", "اجتماع", "عرض", "فوز", "خسارة", "تجاهل")
WON, LOST = "فوز", "خسارة"

# حقول لا يجوز أن يحملها السجل إطلاقاً — تُفحص في --check
FORBIDDEN_HINTS = ("ريال", "sar", "جوال", "+966", "@gmail", "@hotmail")


def _rows(path: Path) -> list:
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
             if not ln.lstrip().startswith("#")]
    return [r for r in csv.DictReader(lines) if r.get("id")]


def load_log() -> list:
    return _rows(LOG)


def load_queue() -> dict:
    return {str(r["id"]): r for r in _rows(QUEUE)}


def append(entry: dict) -> None:
    existing = load_log()
    entry["id"] = str(max((int(r["id"]) for r in existing if r["id"].isdigit()), default=0) + 1)
    header = [ln for ln in LOG.read_text(encoding="utf-8").splitlines()
              if ln.lstrip().startswith("#")] if LOG.exists() else []
    with LOG.open("w", newline="", encoding="utf-8") as f:
        for ln in header:
            f.write(ln + "\n")
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(existing + [entry])
    print(f"سُجّلت الفرصة #{entry['id']} في {rel(LOG)}")


def update(entry_id: str, **changes) -> None:
    rows = load_log()
    hit = next((r for r in rows if str(r["id"]) == str(entry_id)), None)
    if not hit:
        sys.exit(f"لا توجد فرصة بالرقم {entry_id}")
    hit.update({k: v for k, v in changes.items() if v})
    header = [ln for ln in LOG.read_text(encoding="utf-8").splitlines()
              if ln.lstrip().startswith("#")]
    with LOG.open("w", newline="", encoding="utf-8") as f:
        for ln in header:
            f.write(ln + "\n")
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"حُدِّثت الفرصة #{entry_id}: " + "، ".join(f"{k}={v}" for k, v in changes.items() if v))


# ───────────────────────────── التحليل ─────────────────────────────

def by_pillar(log: list, queue: dict) -> dict:
    """ثقل الفرص المنسوبة لكل عمود محتوى."""
    out: dict = defaultdict(lambda: {"count": 0, "weight": 0.0, "won": 0, "untracked": 0})
    for row in log:
        post = queue.get(str(row.get("source_post") or ""))
        pillar = (post or {}).get("pillar") or "_غير_منسوب"
        try:
            w = float(row.get("weight") or 1)
        except ValueError:
            w = 1.0
        bucket = out[pillar]
        bucket["count"] += 1
        bucket["weight"] += w
        bucket["won"] += row.get("stage") == WON
        bucket["untracked"] += not post
    return dict(out)


def inbound_signal(log: list, queue: dict, min_events: int = 2) -> dict:
    """نسبة ثقل الفرص لكل عمود إلى متوسط الأعمدة — إشارة تعلّم مستقلة عن التفاعل.

    الأعمدة التي لم تبلغ الحد الأدنى من الأحداث تبقى محايدة: فرصة واحدة ليست نمطاً.
    """
    stats = {p: v for p, v in by_pillar(log, queue).items() if not p.startswith("_")}
    eligible = {p: v["weight"] for p, v in stats.items() if v["count"] >= min_events}
    if not eligible:
        return {}
    avg = sum(eligible.values()) / len(eligible)
    return {p: round(w / avg, 3) for p, w in eligible.items()} if avg else {}


def funnel(log: list) -> dict:
    return Counter(r.get("stage") or "جديد" for r in log)


def channels(log: list) -> Counter:
    return Counter(r.get("channel") or "other" for r in log)


def kinds(log: list) -> Counter:
    return Counter(r.get("kind") or "—" for r in log)


def privacy_warnings(log: list) -> list:
    """السجل لا يجوز أن يحمل أسماء أو أرقاماً أو مبالغ."""
    out = []
    for row in log:
        blob = " ".join(str(row.get(k, "")) for k in ("label", "notes")).lower()
        found = [h for h in FORBIDDEN_HINTS if h in blob]
        if found:
            out.append((row["id"], found))
    return out


def build_report(log: list, queue: dict, persona: dict) -> str:
    labels = {k: v["label_ar"] for k, v in persona["content_pillars"].items()}
    stats = by_pillar(log, queue)
    ranked = sorted(stats.items(), key=lambda kv: -kv[1]["weight"])
    f, ch, kd = funnel(log), channels(log), kinds(log)
    signal = inbound_signal(log, queue)

    lines = [f"# تقرير الفرص الواردة — {datetime.now():%Y-%m-%d}", "",
             f"إجمالي الفرص المسجّلة: **{len(log)}** · "
             f"منسوبة إلى منشور: **{sum(1 for r in log if queue.get(str(r.get('source_post') or '')))}**",
             "", "## أي محتوى جلب فرصاً؟", "",
             "| العمود | عدد الفرص | الثقل | فوز | إشارة التعلّم |", "|---|---|---|---|---|"]
    for pillar, v in ranked:
        name = labels.get(pillar, pillar if not pillar.startswith("_") else "غير منسوب لمنشور")
        sig = f"{signal[pillar]}×" if pillar in signal else "—"
        lines.append(f"| {name} | {v['count']} | {v['weight']:.0f} | {v['won']} | {sig} |")
    if not ranked:
        lines.append("| — | — | — | — | — |")

    lines += ["", "## مسار الفرص", ""]
    lines += [f"- {stage}: {f.get(stage, 0)}" for stage in STAGES if f.get(stage)] or ["- لا شيء بعد"]

    won, lost = f.get(WON, 0), f.get(LOST, 0)
    if won + lost:
        lines += ["", f"**نسبة الإغلاق:** {won}/{won + lost} = {won / (won + lost):.0%}"]

    lines += ["", "## القنوات", ""]
    lines += [f"- {c}: {n}" for c, n in ch.most_common()] or ["- لا شيء بعد"]
    lines += ["", "## أنواع الفرص", ""]
    lines += [f"- {k}: {n}" for k, n in kd.most_common()] or ["- لا شيء بعد"]

    warn = privacy_warnings(log)
    if warn:
        lines += ["", "## ⚠ تنبيه سرية", ""]
        lines += [f"- الفرصة #{i}: يبدو أنها تحوي {'، '.join(h)} — احذفه، "
                  "السجل للتحليل لا للبيانات الحساسة" for i, h in warn]

    lines += ["", "---",
              "*وُلّد بـ `automation/attribution.py --report`. "
              "إشارة التعلّم تدخل ترجيح الأعمدة في `feedback.py` — "
              "فيتعلم النظام ما يجلب فرصاً لا ما يجلب إعجابات.*"]
    return "\n".join(lines) + "\n"


# ───────────────────────────── الأوامر ─────────────────────────────

def cmd_log(args) -> None:
    if args.channel not in CHANNELS:
        sys.exit(f"قناة غير معروفة. المتاح: {'، '.join(CHANNELS)}")
    if args.stage and args.stage not in STAGES:
        sys.exit(f"مرحلة غير معروفة. المتاح: {'، '.join(STAGES)}")
    append({"date": args.date or f"{datetime.now():%Y-%m-%d}", "channel": args.channel,
            "kind": args.kind or "استفسار", "label": args.label or "",
            "source_post": args.post or "", "stage": args.stage or "جديد",
            "weight": str(args.weight or 1), "notes": args.notes or ""})


def cmd_report(args) -> None:
    log, queue = load_log(), load_queue()
    if not log:
        print("السجل فارغ. سجّل أول فرصة:\n"
              "  python automation/attribution.py --log --channel linkedin --kind طلب_عرض --post <رقم>")
        return
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(log, queue, load_persona()), encoding="utf-8")
    print(f"التقرير: {rel(REPORT)}  ({len(log)} فرصة)")
    for pillar, v in sorted(by_pillar(log, queue).items(), key=lambda kv: -kv[1]["weight"])[:5]:
        print(f"  {v['weight']:5.0f}  {pillar:24} ({v['count']} فرصة · {v['won']} فوز)")


def main() -> None:
    ap = argparse.ArgumentParser(description="سجل الفرص الواردة وربطها بالمحتوى")
    ap.add_argument("--log", action="store_true", help="تسجيل فرصة جديدة")
    ap.add_argument("--report", action="store_true", help="توليد تقرير الفرص")
    ap.add_argument("--update", metavar="ID", help="تحديث فرصة قائمة")
    ap.add_argument("--channel", choices=CHANNELS)
    ap.add_argument("--kind")
    ap.add_argument("--label")
    ap.add_argument("--post", help="رقم المنشور في طابور النشر")
    ap.add_argument("--stage", choices=STAGES)
    ap.add_argument("--weight", type=int, choices=(1, 2, 3))
    ap.add_argument("--notes")
    ap.add_argument("--date")
    args = ap.parse_args()

    if args.update:
        update(args.update, stage=args.stage, notes=args.notes, weight=args.weight and str(args.weight))
    elif args.log:
        if not args.channel:
            ap.error("--log يحتاج --channel")
        cmd_log(args)
    else:
        cmd_report(args)


if __name__ == "__main__":
    main()
