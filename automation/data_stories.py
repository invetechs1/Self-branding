#!/usr/bin/env python3
"""قصص البيانات — تحويل أرقامك التشغيلية إلى محتوى لا يستطيع أحد نسخه.

يقرأ profile/operations-metrics.yml ويفرض حواجز السرية (§36) برمجياً لا ثقةً:
  • لا مبالغ مالية مطلقة ولا أسماء عملاء أو مشاريع
  • كل رقم يحتاج أساساً (من كم حالة استُخرج) بحد أدنى للتجميع
  • internal لا يخرج في منشور، و never لا يُقرأ إطلاقاً
  • لا نشر آلي لقصة بيانات مهما كان تصنيفها — المراجعة البشرية إلزامية

    python automation/data_stories.py --list     # الجاهز للنشر وما ينقصه
    python automation/data_stories.py --check    # تدقيق كامل مع سبب كل استبعاد
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "profile" / "operations-metrics.yml"

MIN_BASIS = 5                      # أقل عدد حالات يجعل الرقم بياناً لا واقعة فردية
SENSITIVITY = ("safe", "internal", "never")

# مؤشرات مبلغ مالي مطلق — ممنوعة مهما كان التصنيف
MONEY = re.compile(r"(ريال|SAR|ر\.س|مليون|مليار|دولار|\$)", re.I)
# أساس الرقم يجب أن يحمل عدداً: «من 18 مستخلصاً»
BASIS_COUNT = re.compile(r"(\d+)")


def load_metrics() -> list:
    if not METRICS.exists():
        return []
    data = yaml.safe_load(METRICS.read_text(encoding="utf-8")) or {}
    return data.get("metrics") or []


def basis_size(basis: str | None) -> int:
    """عدد الحالات التي بُني عليها الرقم، صفر إن لم يُذكر."""
    if not basis:
        return 0
    numbers = [int(n) for n in BASIS_COUNT.findall(str(basis))]
    return max(numbers) if numbers else 0


def validate(metric: dict) -> tuple[bool, list]:
    """هل يجوز بناء محتوى على هذا الرقم؟ يعيد (صالح، أسباب الرفض)."""
    problems = []
    sens = (metric.get("sensitivity") or "").strip().lower()

    if sens not in SENSITIVITY:
        problems.append(f"تصنيف حساسية غير معروف: {sens or '—'}")
    if sens == "never":
        problems.append("مصنّف never — لا يُستخدم إطلاقاً")
    if sens == "internal":
        problems.append("مصنّف internal — للتقارير الخاصة لا للنشر")

    if metric.get("value") in (None, "", []):
        problems.append("بلا قيمة — املأ value")

    size = basis_size(metric.get("basis"))
    if not metric.get("basis"):
        problems.append("بلا أساس — اذكر من كم حالة استُخرج الرقم")
    elif size == 0:
        problems.append(f"الأساس بلا عدد: «{metric['basis']}»")
    elif size < MIN_BASIS:
        problems.append(f"الأساس {size} حالات فقط (الحد الأدنى {MIN_BASIS}) — قد يكشف مشروعاً بعينه")

    haystack = " ".join(str(metric.get(k, "")) for k in ("label", "value", "unit", "basis", "angle"))
    if MONEY.search(haystack):
        problems.append("يحوي مبلغاً مالياً مطلقاً — حوّله إلى نسبة أو مدة")

    return (not problems), problems


def publishable(metrics: list | None = None) -> list:
    return [m for m in (metrics if metrics is not None else load_metrics()) if validate(m)[0]]


def describe(metric: dict) -> str:
    """صياغة الرقم كما يُذكر في المحتوى — مع أساسه دائماً."""
    unit = metric.get("unit", "")
    value = metric.get("value")
    number = f"{value}{'%' if unit == '%' else ''}" if unit == "%" else f"{value} {unit}".strip()
    return f"{metric['label']}: {number} ({metric.get('basis', '')})".strip()


def cmd_list(args) -> None:
    metrics = load_metrics()
    ready = publishable(metrics)
    print(f"الأرقام: {len(metrics)} · الجاهز للنشر: {len(ready)}\n")
    for m in metrics:
        ok, why = validate(m)
        mark = "✔" if ok else "·"
        print(f" {mark} {m.get('label', m.get('key', '—'))}")
        if ok:
            print(f"      {describe(m)}")
            print(f"      الزاوية: {m.get('angle', '—')}")
        else:
            print(f"      ينقصه: {' | '.join(why)}")
    if not ready:
        print("\nلا رقم جاهزاً بعد. املأ value و basis لثلاثة أرقام تعرفها اليوم،"
              "\nثم: python automation/generate_posts.py --data-story")


def cmd_check(args) -> None:
    metrics = load_metrics()
    blocked = [(m, validate(m)[1]) for m in metrics if not validate(m)[0]]
    print(f"تدقيق السرية: {len(metrics)} رقماً، محجوب {len(blocked)}\n")
    for m, why in blocked:
        print(f"  ✗ {m.get('label', m.get('key'))}")
        for reason in why:
            print(f"      - {reason}")
    if not blocked:
        print("  كل الأرقام تجتاز الحواجز.")
    print(f"\nالقواعد المفروضة برمجياً: حد التجميع {MIN_BASIS} حالات · "
          "منع المبالغ المالية المطلقة · internal و never لا يخرجان")


def main() -> None:
    ap = argparse.ArgumentParser(description="قصص البيانات التشغيلية")
    ap.add_argument("--list", action="store_true", help="عرض الأرقام وحالتها")
    ap.add_argument("--check", action="store_true", help="تدقيق الحواجز وأسباب الحجب")
    args = ap.parse_args()
    if args.check:
        cmd_check(args)
    else:
        cmd_list(args)


if __name__ == "__main__":
    main()
