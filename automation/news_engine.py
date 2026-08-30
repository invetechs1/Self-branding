#!/usr/bin/env python3
"""محرك الاكتشاف والترتيب — الخطوات 1-6 من سير العمل (§38).

    جمع الأخبار → استبعاد غير ذي الصلة → تجميع المكرر → مصداقية المصدر →
    درجة الملاءمة ليحيى → التحقق من الحقائق

يخزّن النتيجة في automation/queue/news.jsonl (سجل تراكمي بلا تكرار)،
ويولّد التقرير الأسبوعي (§47) في analytics/intelligence/.

    python automation/news_engine.py --discover          # دورة اكتشاف كاملة
    python automation/news_engine.py --top 10            # أهم القصص المخزّنة
    python automation/news_engine.py --report            # تقرير الاستخبارات الأسبوعي
    python automation/news_engine.py --check-sources     # فحص صلاحية روابط RSS

لا يكتب منشوراً واحداً — الكتابة مهمة generate_posts.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from persona import (Story, cluster_stories, detect_opportunities, detect_trends,
                     load_learning, load_persona, score_story)

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "automation" / "sources.yml"
# كثير من المواقع الإخبارية ترفض وكيل بايثون الافتراضي
USER_AGENT = "Mozilla/5.0 (compatible; YahyaBrandEngine/1.0; +personal content research)"
NEWS_FILE = ROOT / "automation" / "queue" / "news.jsonl"
REPORT_DIR = ROOT / "analytics" / "intelligence"


def _parse_date(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def fetch_feeds(limit_per_feed: int = 25) -> list:
    """يقرأ كل التغذيات المعرّفة في sources.yml — فشل تغذية لا يوقف البقية."""
    try:
        import feedparser
    except ImportError:
        sys.exit("ينقص feedparser — شغّل: pip install -r automation/requirements.txt")

    feeds = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))["feeds"]
    stories = []
    for feed in feeds:
        try:
            parsed = feedparser.parse(feed["url"], agent=USER_AGENT)
        except Exception as e:  # noqa: BLE001 — مصدر معطّل لا يوقف الدورة
            print(f"  تعذّر: {feed['name']} — {e}")
            continue
        if not parsed.entries:
            print(f"  فارغ/معطّل: {feed['name']} — {_feed_error(parsed)}")
            continue
        for entry in parsed.entries[:limit_per_feed]:
            summary = (entry.get("summary", "") or "")[:600]
            stories.append(Story(
                title=entry.get("title", "").strip(),
                summary=summary,
                url=entry.get("link", ""),
                source=feed["name"],
                source_type=feed.get("type", "unknown_website"),
                published=_parse_date(entry),
                meta={"feed_region": feed.get("region", "global")},
            ))
        print(f"  {feed['name']}: {min(len(parsed.entries), limit_per_feed)} خبراً")
    return stories


def _feed_error(parsed) -> str:
    """سبب فشل التغذية بصيغة مفهومة: حجب، أو رابط خاطئ، أو تغيّر في الموقع."""
    status = getattr(parsed, "status", None)
    if status and status >= 400:
        return f"HTTP {status}"
    if getattr(parsed, "bozo", False):
        return str(getattr(parsed, "bozo_exception", ""))[:90]
    return "لا عناصر في التغذية"


def load_stored() -> list:
    if not NEWS_FILE.exists():
        return []
    return [Story.from_dict(json.loads(line)) for line in
            NEWS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_stories(stories: list) -> None:
    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NEWS_FILE.open("w", encoding="utf-8") as f:
        for s in stories:
            f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")


def prune(stories: list, persona: dict, now: datetime) -> list:
    """يحذف ما تجاوز نافذة الحداثة القصوى (§20) لإبقاء السجل خفيفاً."""
    max_age = timedelta(hours=persona["thresholds"]["freshness_max_age_hours"] * 4)
    return [s for s in stories if not s.published or now - s.published <= max_age]


def discover(args) -> None:
    persona, now, learning = load_persona(), datetime.now(timezone.utc), load_learning()
    threshold = persona["thresholds"]["pipeline_entry"]

    print("جمع الأخبار من المصادر ...")
    fresh = fetch_feeds(args.limit)
    stored = load_stored()
    seen = {s.url for s in stored if s.url}
    new = [s for s in fresh if s.url and s.url not in seen and s.title]
    print(f"\nوصل {len(fresh)} خبراً، منها {len(new)} جديد.")

    kept = []
    for story in new:
        score_story(story, persona, now, learning)
        if story.scores["total"] >= threshold:
            story.meta["opportunities"] = detect_opportunities(story)
            kept.append(story)
    print(f"تجاوز عتبة الملاءمة ({threshold}): {len(kept)} قصة.")

    allstories = prune(stored + kept, persona, now)
    save_stories(allstories)

    clusters = cluster_stories(kept, persona)
    print(f"بعد تجميع المكرر: {len(clusters)} عنقود قصة.\n")
    for c in clusters[:args.top or 10]:
        p = c["primary"]
        print(f"[{p.scores['total']:5.1f}] {p.title[:95]}")
        print(f"        {p.meta['pillar']} · {p.meta['region']} · مصادر: {c['source_count']}"
              f" · ثقة الحقائق: {c['fact_confidence']}"
              + (f" · فرص: {', '.join(o['label'] for o in p.meta.get('opportunities', []))}"
                 if p.meta.get("opportunities") else ""))
    print(f"\nالسجل: {NEWS_FILE.relative_to(ROOT)} ({len(allstories)} قصة)")
    print("الخطوة التالية: python automation/generate_posts.py --from-news")


def show_top(args) -> None:
    persona = load_persona()
    stories = sorted(load_stored(), key=lambda s: -s.scores.get("total", 0))[:args.top or 10]
    for s in stories:
        print(f"[{s.scores.get('total', 0):5.1f}] {s.meta.get('pillar', '?'):24} {s.title[:80]}")
        print(f"        {s.source} · {s.url}")


def weekly_report(args) -> None:
    """§47: تقرير الاستخبارات الأسبوعي."""
    persona, now = load_persona(), datetime.now(timezone.utc)
    week = [s for s in load_stored() if s.published and now - s.published <= timedelta(days=7)]
    if not week:
        sys.exit("لا توجد قصص في آخر 7 أيام — شغّل --discover أولاً.")

    clusters = cluster_stories(week, persona)
    trends = detect_trends(clusters, persona)
    deep = persona["thresholds"]["deep_dive"]

    def by_pillar(name):
        return [c for c in clusters if c["primary"].meta.get("pillar") == name]

    def bullets(items, n=10):
        out = []
        for c in items[:n]:
            p = c["primary"]
            out.append(f"- **[{p.scores['total']:.0f}]** [{p.title}]({p.url}) — "
                       f"{p.source} · {p.meta.get('pillar')} · ثقة الحقائق {c['fact_confidence']}")
        return "\n".join(out) or "- لا شيء هذا الأسبوع"

    opps = [(c, o) for c in clusters for o in c["primary"].meta.get("opportunities", [])]
    saudi = [c for c in clusters if c["primary"].meta.get("region") == "saudi_arabia"]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{now:%Y}-W{now.isocalendar().week:02d}.md"
    path.write_text(f"""# تقرير الاستخبارات الأسبوعي — {now:%Y-%m-%d}

مسح {len(week)} قصة ذات صلة، جُمّعت في {len(clusters)} حدثاً مستقلاً.

## 1. أهم 10 تطورات
{bullets(clusters, 10)}

## 2. أفضل 5 فرص محتوى
{bullets([c for c in clusters if c['primary'].scores['total'] >= deep] or clusters, 5)}

## 3. أهم 3 فرص أعمال (§45)
{chr(10).join(f"- **{o['label']}** — [{c['primary'].title}]({c['primary'].url})" for c, o in opps[:3]) or "- لا شيء هذا الأسبوع"}

## 4. الاتجاهات المرصودة (§46)
{chr(10).join(f"- **{t['headline']}** (متوسط الدرجة {t['avg_score']})" for t in trends[:3]) or "- لا اتجاه واضح بعد"}

## 5. التقنية
{bullets(by_pillar('ai_technology'), 3)}

## 6. الإنشاءات والهندسة
{bullets(by_pillar('construction_engineering'), 3)}

## 7. الفرصة السعودية
{bullets(saudi, 3)}

## 8. الموضوع المقترح للتعمّق
{(lambda c: f"**{c['primary'].title}** — درجة {c['primary'].scores['total']:.0f}، "
  f"تقاطع {c['primary'].meta.get('intersection') or c['primary'].meta.get('pillar')}. "
  f"يستحق مقالاً أو ثريداً تحليلياً." if clusters else "لا شيء")(clusters[0] if clusters else None)}

---
*وُلّد آلياً بواسطة `automation/news_engine.py --report`. راجع قبل الاعتماد.*
""", encoding="utf-8")
    print(f"التقرير: {path.relative_to(ROOT)}")


def check_sources(args) -> None:
    try:
        import feedparser
    except ImportError:
        sys.exit("ينقص feedparser — شغّل: pip install -r automation/requirements.txt")
    for feed in yaml.safe_load(SOURCES.read_text(encoding="utf-8"))["feeds"]:
        try:
            parsed = feedparser.parse(feed["url"], agent=USER_AGENT)
            n, why = len(parsed.entries), _feed_error(parsed)
        except Exception as e:  # noqa: BLE001
            n, why = 0, str(e)[:90]
        print(f"{'OK  ' if n else 'FAIL'} {n:3d} — {feed['name']}: {feed['url']}"
              + ("" if n else f"\n           السبب: {why}"))


def main() -> None:
    ap = argparse.ArgumentParser(description="محرك اكتشاف وترتيب الأخبار")
    ap.add_argument("--discover", action="store_true", help="دورة اكتشاف وترتيب كاملة")
    ap.add_argument("--top", type=int, default=0, help="عرض أهم N قصة مخزّنة")
    ap.add_argument("--report", action="store_true", help="توليد التقرير الأسبوعي")
    ap.add_argument("--check-sources", action="store_true", help="فحص روابط RSS")
    ap.add_argument("--limit", type=int, default=25, help="حد الأخبار لكل مصدر")
    args = ap.parse_args()

    if args.check_sources:
        check_sources(args)
    elif args.discover:
        discover(args)
    elif args.report:
        weekly_report(args)
    elif args.top:
        show_top(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
