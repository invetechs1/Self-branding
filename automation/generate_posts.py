#!/usr/bin/env python3
"""مولّد المحتوى — الخطوات 7-10 من سير العمل (§38).

    تحديد الزاوية → توليد رؤية يحيى → نسخ خاصة بكل منصة → فحوص السلامة

وضعان:
  --from-news    يحوّل أهم عناقيد الأخبار (من news_engine) إلى محتوى (News + Insight)
  --week         يولّد أسبوع محتوى من بنك الأفكار (تعليمي/سردي)

كل مخرج يحمل: العمود، نوع المحتوى، اللغة، مستوى الاعتماد (أخضر/أصفر/أحمر)، المصدر، درجة الملاءمة.
الوقائع الشخصية تُؤخذ حصراً من profile/facts.yml — والمراجعة البشرية تبقى شرط النشر.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
import yaml

from persona import (build_system_prompt, classify_approval, cluster_stories, is_repeat,
                     load_facts, load_learning, load_persona, mix_deficit, score_story)
import news_engine

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "automation" / "queue" / "queue.csv"
QUEUE_FIELDS = ["id", "date", "time", "platform", "pillar", "content_type", "language",
                "approval_level", "review_notes", "relevance", "source_url", "content",
                "media_note", "status"]

# إيقاع النشر الأسبوعي (اليوم: المنصات) — يطابق strategy/04
WEEKLY_RHYTHM = {0: ["twitter_thread"], 1: ["article"], 2: ["instagram_carousel"],
                 3: ["tiktok_script"], 6: ["linkedin_post"]}
DAILY_TWEET_DAYS = range(7)
POST_TIMES = {"twitter_thread": "08:00", "twitter": "20:30", "article": "10:00",
              "instagram_carousel": "18:00", "tiktok_script": "19:00", "linkedin_post": "08:30"}
NEWS_PLATFORMS = ["linkedin_post", "twitter_thread", "twitter"]


def load_config() -> dict:
    cfg_path = ROOT / "automation" / "config.yml"
    if not cfg_path.exists():
        sys.exit("لا يوجد config.yml — انسخ config.example.yml وعبّئ المفاتيح.")
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


# ────────────────────── الطابور: قراءة، ترحيل، كتابة ──────────────────────

def read_queue() -> list:
    if not QUEUE.exists():
        return []
    return list(csv.DictReader(QUEUE.open(encoding="utf-8")))


def append_to_queue(rows: list) -> None:
    """يضيف للطابور، ويرحّل الملف القديم إلى المخطط الجديد إن لزم."""
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    existing = read_queue()
    if existing and set(existing[0].keys()) != set(QUEUE_FIELDS):
        existing = [{f: r.get(f, "") for f in QUEUE_FIELDS} for r in existing]
        print("رُحِّل queue.csv إلى المخطط الجديد (أعمدة العمود/الاعتماد/المصدر).")
    with QUEUE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
        w.writeheader()
        w.writerows(existing + rows)


def published_pillar_counts(queue: list) -> dict:
    counts: dict = {}
    for row in queue:
        if row.get("pillar") and row.get("status") in ("posted", "approved", "manual"):
            counts[row["pillar"]] = counts.get(row["pillar"], 0) + 1
    return counts


def previous_contents(queue: list, limit: int = 60) -> list:
    return [r.get("content", "") for r in queue[-limit:] if r.get("content")]


# ────────────────────────── التوليد ──────────────────────────

def platform_spec(persona: dict, platform: str) -> str:
    spec = persona["platforms"].get(platform, {})
    parts = [f"الطول: {spec.get('length', '')}"]
    if spec.get("structure"):
        parts.append("البنية: " + " ← ".join(spec["structure"]))
    if spec.get("style"):
        parts.append("الأسلوب: " + spec["style"])
    if platform == "twitter_thread":
        parts.append("افصل بين التغريدات بسطر يحوي --- فقط.")
    return " | ".join(parts)


def generate(client, model, system, user_prompt: str, max_tokens: int = 4000) -> str:
    msg = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                 messages=[{"role": "user", "content": user_prompt}])
    return msg.content[0].text.strip()


def news_prompt(persona: dict, facts: dict, cluster: dict, platform: str, language: str) -> str:
    p = cluster["primary"]
    sources = "\n".join(f"  - {m.source} ({m.source_type}) — {m.title} :: {m.url}"
                        for m in [p] + cluster["supporting"])
    return f"""الحدث (عنقود قصة واحد — لا تكتب عنه أكثر من زاوية واحدة):

العنوان: {p.title}
الملخص: {p.summary}
التاريخ: {p.published:%Y-%m-%d} | العمود: {p.meta.get('pillar')} | المنطقة: {p.meta.get('region')}
درجة الملاءمة: {p.scores['total']} | ثقة الحقائق: {cluster['fact_confidence']}
المصادر:
{sources}
فرص مرصودة: {', '.join(o['label'] for o in p.meta.get('opportunities', [])) or 'لا يوجد'}

ملف الحقائق (المصدر الوحيد لأي معلومة شخصية):
```yaml
{yaml.dump(facts, allow_unicode=True)}
```

اكتب منشور "خبر + رؤية" (News + Insight) لمنصة {platform} باللغة {'العربية' if language == 'ar' else 'الإنجليزية'}.
{platform_spec(persona, platform)}

اتبع هذا التسلسل داخلياً ثم أخرج النص النهائي فقط:
1. ما الذي حدث فعلاً؟ (سطر واحد بلا تهويل، وبالأرقام الواردة في المصادر فقط)
2. لماذا يهم؟ اختر زاوية واحدة من: فرصة عمل، أثر على الإنشاءات، أثر عقاري، فرصة ذكاء اصطناعي،
   ملاءمة للسوق السعودي، أثر على الإنتاجية، نموذج عمل جديد، تهديد تنافسي.
3. طبقة رؤية يحيى: أجب عن أحد هذه الأسئلة بوضوح — {' / '.join(persona['insight_questions'][:5])}
4. اختم بخلاصة عملية أو سؤال ذكي (بلا عبارات تحفيزية).

ممنوع: تلخيص المقال حرفياً، اختراع رقم غير وارد أعلاه، ادعاء تجربة شخصية غير موجودة في ملف الحقائق،
هاشتاقات غير ضرورية، تقديم التوقع كحقيقة."""


def idea_prompt(persona: dict, facts: dict, idea: str, platform: str, pillar: str, language: str) -> str:
    return f"""الفكرة: {idea}
العمود المستهدف: {pillar} ({persona['content_pillars'][pillar]['label_ar']})

ملف الحقائق (المصدر الوحيد لأي معلومة شخصية):
```yaml
{yaml.dump(facts, allow_unicode=True)}
```

اكتب محتوى لمنصة {platform} باللغة {'العربية' if language == 'ar' else 'الإنجليزية'}.
{platform_spec(persona, platform)}

اربط الفكرة بخبرة تشغيلية حقيقية من ملف الحقائق إن وُجدت، وإلا اجعلها تعليمية عامة.
أضف زاوية سعودية/خليجية عملية إن كانت حقيقية. أخرج النص النهائي فقط."""


def build_row(uid: int, date, platform: str, content: str, persona: dict, *,
              pillar: str, content_type: str, language: str, relevance: str = "",
              source_url: str = "", fact_conf: float = 1.0, previous: list) -> dict:
    level, reasons = classify_approval(content, persona, fact_conf)
    if is_repeat(content, previous):
        level = "yellow" if level == "green" else level
        reasons.append("يشبه منشوراً سابقاً (§43) — غيّر الخطّاف أو الزاوية")
    return {
        "id": uid, "date": f"{date:%Y-%m-%d}", "time": POST_TIMES.get(platform, "12:00"),
        "platform": platform, "pillar": pillar, "content_type": content_type, "language": language,
        "approval_level": level, "review_notes": " | ".join(reasons), "relevance": relevance,
        "source_url": source_url, "content": content,
        "media_note": "صمّم البصري وفق قالب Canva الموحد"
                      if platform in ("instagram_carousel", "tiktok_script") else "",
        "status": "draft",
    }


# ────────────────────────── الأوضاع ──────────────────────────

def run_from_news(args, client, model, persona, facts) -> list:
    """يحوّل أهم عناقيد الأخبار إلى منشورات (§38 خطوات 7-10)."""
    stories = news_engine.load_stored()
    if not stories:
        sys.exit("لا توجد أخبار مخزّنة — شغّل: python automation/news_engine.py --discover")

    now = datetime.now(timezone.utc)
    learning = load_learning()
    for s in stories:
        score_story(s, persona, now, learning)   # إعادة التسعير: الحداثة والتعلّم يتغيران
    clusters = [c for c in cluster_stories(stories, persona)
                if c["primary"].scores["total"] >= persona["thresholds"]["pipeline_entry"]]

    queue = read_queue()
    used_urls = {r.get("source_url") for r in queue if r.get("source_url")}
    clusters = [c for c in clusters if c["primary"].url not in used_urls][:args.count]
    if not clusters:
        sys.exit("كل القصص المؤهلة استُخدمت في محتوى سابق — شغّل --discover لجلب أحدث.")

    # ضبط المزيج (§26): العمود الأبعد عن حصته يتصدر ترتيب المعالجة
    order = mix_deficit(published_pillar_counts(queue), persona)
    clusters.sort(key=lambda c: order.index(c["primary"].meta.get("pillar", order[0]))
                  if c["primary"].meta.get("pillar") in order else 99)

    previous, rows = previous_contents(queue), []
    system = build_system_prompt(persona, facts, args.language)
    uid, start = int(datetime.now().timestamp()), datetime.now()

    for i, cluster in enumerate(clusters):
        p = cluster["primary"]
        print(f"\n[{p.scores['total']:.0f}] {p.title[:80]}")
        for platform in args.platforms:
            print(f"    توليد {platform} ...")
            content = generate(client, model, system,
                               news_prompt(persona, facts, cluster, platform, args.language))
            uid += 1
            row = build_row(uid, start + timedelta(days=i), platform, content, persona,
                            pillar=p.meta.get("pillar", "ai_technology"), content_type="news_insight",
                            language=args.language, relevance=str(p.scores["total"]),
                            source_url=p.url, fact_conf=cluster["fact_confidence"], previous=previous)
            rows.append(row)
            previous.append(content)
            print(f"      → {row['approval_level'].upper()}"
                  + (f" — {row['review_notes']}" if row["review_notes"] else ""))
    return rows


def next_idea() -> str:
    bank = ROOT / "content" / "idea-bank.md"
    lines = bank.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\d+)\. (?!✔)(.+)$", line.strip())
        if m:
            lines[i] = f"{m.group(1)}. ✔ {m.group(2)}"
            bank.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return m.group(2)
    sys.exit("بنك الأفكار مستهلك بالكامل — أضف أفكاراً جديدة إلى content/idea-bank.md")


def run_week(args, client, model, persona, facts) -> list:
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        today = datetime.now()
        start = today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    idea = next_idea()
    queue = read_queue()
    pillar = mix_deficit(published_pillar_counts(queue), persona)[0]
    print(f"فكرة الأسبوع: {idea}\nالعمود الأولى بالتغطية هذا الأسبوع: {pillar}")

    previous, rows = previous_contents(queue), []
    system = build_system_prompt(persona, facts, args.language)
    uid = int(start.timestamp())

    for day_offset in range(7):
        date = start + timedelta(days=day_offset)
        formats = list(WEEKLY_RHYTHM.get(date.weekday(), []))
        if date.weekday() in DAILY_TWEET_DAYS:
            formats.append("twitter")
        for platform in formats:
            print(f"  توليد {platform} ليوم {date:%Y-%m-%d} ...")
            content = generate(client, model, system,
                               idea_prompt(persona, facts, idea, platform, pillar, args.language))
            uid += 1
            row = build_row(uid, date, platform, content, persona, pillar=pillar,
                            content_type="educational", language=args.language, previous=previous)
            rows.append(row)
            previous.append(content)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="مولّد المحتوى المدفوع بالشخصية")
    ap.add_argument("--from-news", action="store_true", help="توليد من عناقيد الأخبار المرتّبة")
    ap.add_argument("--week", action="store_true", help="توليد أسبوع من بنك الأفكار")
    ap.add_argument("--count", type=int, default=3, help="عدد القصص في وضع الأخبار")
    ap.add_argument("--platforms", nargs="+", default=NEWS_PLATFORMS,
                    help=f"المنصات في وضع الأخبار (الافتراضي: {' '.join(NEWS_PLATFORMS)})")
    ap.add_argument("--language", choices=["ar", "en"], default=None, help="لغة المحتوى")
    ap.add_argument("--start", help="تاريخ بداية الأسبوع YYYY-MM-DD")
    args = ap.parse_args()

    if not (args.from_news or args.week):
        ap.error("اختر --from-news أو --week")

    cfg, persona, facts = load_config(), load_persona(), load_facts()
    settings, news_cfg = cfg.get("settings", {}), cfg.get("news", {})
    args.language = (args.language or settings.get("default_language")
                     or persona["voice"].get("default_language", "ar"))
    if args.count == ap.get_default("count") and news_cfg.get("posts_per_run"):
        args.count = int(news_cfg["posts_per_run"])
    if args.platforms == NEWS_PLATFORMS and news_cfg.get("platforms"):
        args.platforms = list(news_cfg["platforms"])
    client = anthropic.Anthropic(api_key=cfg["anthropic"]["api_key"])
    model = cfg["anthropic"].get("model", "claude-sonnet-5")

    rows = run_from_news(args, client, model, persona, facts) if args.from_news \
        else run_week(args, client, model, persona, facts)

    append_to_queue(rows)
    levels = {}
    for r in rows:
        levels[r["approval_level"]] = levels.get(r["approval_level"], 0) + 1
    print(f"\nأُضيفت {len(rows)} مسودة إلى {QUEUE.relative_to(ROOT)} — "
          + "، ".join(f"{k}: {v}" for k, v in levels.items()))
    print("راجعها بصوتك، ثم غيّر status إلى approved. الأحمر لا يُنشر إلا باعتماد يدوي صريح.")


if __name__ == "__main__":
    main()
