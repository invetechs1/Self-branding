#!/usr/bin/env python3
"""رزنامة المناسبات السعودية — تُنبّه قبل المناسبة لا بعدها.

تقرأ content/saudi-calendar.yml وتحسب ما يقترب: مناسبات بتاريخ ميلادي ثابت
(اليوم الوطني، يوم التأسيس...) ومناسبات هجرية (رمضان، العيدان) بتقويم أم القرى.

    python automation/calendar_sa.py                # ما يقترب خلال 45 يوماً
    python automation/calendar_sa.py --days 120     # أفق أبعد
    python automation/calendar_sa.py --due          # ما حان وقت الكتابة عنه الآن
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CALENDAR = ROOT / "content" / "saudi-calendar.yml"


def load_calendar() -> dict:
    if not CALENDAR.exists():
        return {"occasions": [], "recurring_reminders": []}
    return yaml.safe_load(CALENDAR.read_text(encoding="utf-8")) or {}


def _hijri_to_gregorian(h_month: int, h_day: int, around: date) -> date | None:
    """تاريخ ميلادي لمناسبة هجرية في أقرب سنة هجرية قادمة. None إن تعذّر الحساب."""
    try:
        from hijridate import Gregorian, Hijri
    except ImportError:
        return None
    h_year = Gregorian(around.year, around.month, around.day).to_hijri().year
    for year in (h_year, h_year + 1):
        try:
            g = Hijri(year, h_month, h_day).to_gregorian()
        except (ValueError, OverflowError):
            continue
        candidate = date(g.year, g.month, g.day)
        if candidate >= around:
            return candidate
    return None


def _next_fixed(month: int, day: int, today: date) -> date:
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:          # 29 فبراير في سنة غير كبيسة
            continue
        if candidate >= today:
            return candidate
    return date(today.year + 1, month, day)


def upcoming(days_ahead: int = 45, today: date | None = None, cal: dict | None = None) -> list:
    """المناسبات القادمة خلال الأفق المطلوب، مرتبة بالأقرب."""
    today = today or date.today()
    cal = cal if cal is not None else load_calendar()
    out, unresolved = [], []

    for occ in cal.get("occasions", []):
        kind = occ.get("kind", "fixed")
        if kind == "hijri":
            when = _hijri_to_gregorian(occ["hijri_month"], occ["hijri_day"], today)
            if when is None:
                unresolved.append(occ["name"])
                continue
        else:
            when = _next_fixed(occ["month"], occ["day"], today)

        away = (when - today).days
        if away > days_ahead:
            continue
        lead = int(occ.get("lead_days", 7))
        out.append({
            "key": occ.get("key", ""), "name": occ["name"], "date": when, "days_away": away,
            "lead_days": lead, "due": away <= lead, "kind": kind,
            "pillar": occ.get("pillar", "occasions"), "angle": occ.get("angle", ""),
            "window_days": occ.get("window_days", 0),
        })

    out.sort(key=lambda o: o["days_away"])
    if unresolved:
        out.append({"key": "_warning", "name": "تعذّر حساب مناسبات هجرية", "date": today,
                    "days_away": 0, "lead_days": 0, "due": False, "kind": "warning",
                    "pillar": "occasions",
                    "angle": "ثبّت المكتبة: pip install hijridate — المناسبات المتأثرة: "
                             + "، ".join(unresolved), "window_days": 0})
    return out


def due_now(today: date | None = None, cal: dict | None = None) -> list:
    """ما دخل نافذة الكتابة: حان وقت تجهيز محتواه."""
    return [o for o in upcoming(120, today, cal) if o["due"] and o["kind"] != "warning"]


def as_lines(items: list) -> list:
    lines = []
    for o in items:
        if o["kind"] == "warning":
            lines.append(f"  ⚠ {o['name']} — {o['angle']}")
            continue
        when = "اليوم" if o["days_away"] == 0 else f"بعد {o['days_away']} يوماً"
        mark = "◆ حان وقت الكتابة" if o["due"] else "·"
        lines.append(f"  {mark} {o['name']} ({o['date']:%Y-%m-%d} — {when})")
        if o["angle"]:
            lines.append(f"      الزاوية: {o['angle']}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description="المناسبات السعودية القادمة")
    ap.add_argument("--days", type=int, default=45, help="أفق الأيام (افتراضي 45)")
    ap.add_argument("--due", action="store_true", help="ما حان وقت الكتابة عنه فقط")
    args = ap.parse_args()

    items = due_now() if args.due else upcoming(args.days)
    if not items:
        print("لا مناسبات ضمن هذا الأفق.")
        return
    print(f"المناسبات {'المستحقة الآن' if args.due else f'خلال {args.days} يوماً'}:\n")
    print("\n".join(as_lines(items)))
    reminders = load_calendar().get("recurring_reminders", [])
    if reminders and not args.due:
        print("\nمواعيد إدارية متكررة:")
        for r in reminders:
            print(f"  · {r['name']} ({r['cadence']}) — {r['angle']}")


if __name__ == "__main__":
    main()
