#!/usr/bin/env python3
"""توليد محتوى أسبوع كامل من ملف الحقائق وبنك الأفكار.

فكرة واحدة من بنك الأفكار → 5 صيغ (ثريد X، مقال، كاروسيل انستقرام،
سكربت تيك توك، منشور لينكدإن) → تُضاف كمسودات إلى queue/queue.csv.

الأرقام والإنجازات تُستمد حصراً من profile/facts.yml — التعليمات للنموذج
تمنع اختراع وقائع، والمراجعة البشرية قبل النشر إلزامية.
"""

import argparse
import csv
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import yaml

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "automation" / "queue" / "queue.csv"
QUEUE_FIELDS = ["id", "date", "time", "platform", "content", "media_note", "status"]

# إيقاع النشر الأسبوعي (اليوم: المنصات) — يطابق strategy/04
WEEKLY_RHYTHM = {
    0: ["twitter_thread"],            # الاثنين: ثريد
    1: ["article"],                   # الثلاثاء: مقال للموقع
    2: ["instagram_carousel"],        # الأربعاء
    3: ["tiktok_script"],             # الخميس
    6: ["linkedin_post"],             # الأحد
}
DAILY_TWEET_DAYS = range(7)           # تغريدة مفردة يومياً

POST_TIMES = {"twitter_thread": "08:00", "twitter": "20:30", "article": "10:00",
              "instagram_carousel": "18:00", "tiktok_script": "19:00",
              "linkedin_post": "08:30"}

SYSTEM_PROMPT = """أنت كاتب محتوى عربي محترف لعلامة شخصية في إدارة المشاريع وريادة الأعمال.

قواعد صارمة لا تُكسر:
1. الحقائق والأرقام والإنجازات الشخصية تُؤخذ حصراً من ملف الحقائق المرفق.
   يُمنع اختراع أي إنجاز أو رقم أو قصة شخصية غير موجودة فيه.
   إن كان الملف لا يحتوي ما يلزم لقالب "شخصي"، حوّل الزاوية إلى تعليمية عامة.
2. الإحصائيات العامة عن السوق تُذكر فقط إن كنت متأكداً منها، مع صيغة حذرة.
3. عربية بيضاء، جمل قصيرة، عملي ومباشر، بدون عبارات تحفيزية إنشائية.
4. اتبع بنية القالب المطلوب حرفياً."""

FORMAT_SPECS = {
    "twitter_thread": "ثريد X من 6-9 تغريدات، افصل بين التغريدات بسطر يحوي --- فقط، كل تغريدة أقل من 270 حرفاً، وفق قوالب content/templates/twitter-threads.md",
    "twitter": "تغريدة مفردة واحدة أقل من 270 حرفاً، ملاحظة خبيرة أو سؤال تفاعلي",
    "article": "مقال 900-1200 كلمة بصيغة Markdown بعنوان يطابق صيغة بحث حقيقية، مقسم بعناوين فرعية",
    "instagram_carousel": "نصوص 8 شرائح كاروسيل، كل شريحة: عنوان قصير + جملتان كحد أقصى، ثم كابشن للمنشور",
    "tiktok_script": "سكربت فيديو 45 ثانية: [خطّاف 3 ثوان] ثم [المحتوى] ثم [الخاتمة]، بلغة محكية مفهومة",
    "linkedin_post": "منشور لينكدإن 150-250 كلمة، مهني، ينتهي بسؤال للنقاش",
}


def load_config():
    cfg_path = ROOT / "automation" / "config.yml"
    if not cfg_path.exists():
        sys.exit("لا يوجد config.yml — انسخ config.example.yml وعبّئ المفاتيح.")
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def load_facts():
    facts = yaml.safe_load((ROOT / "profile" / "facts.yml").read_text(encoding="utf-8"))
    if not facts.get("identity", {}).get("name_ar"):
        print("تحذير: profile/facts.yml شبه فارغ — المحتوى سيكون تعليمياً عاماً بلا قصص شخصية.")
    return facts


def next_idea():
    """أول فكرة غير مستهلكة من بنك الأفكار (يُعلَّم المستهلك بـ ✔)."""
    bank = ROOT / "content" / "idea-bank.md"
    lines = bank.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\d+)\. (?!✔)(.+)$", line.strip())
        if m:
            lines[i] = f"{m.group(1)}. ✔ {m.group(2)}"
            bank.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return m.group(2)
    sys.exit("بنك الأفكار مستهلك بالكامل — أضف أفكاراً جديدة إلى content/idea-bank.md")


def generate(client, model, facts, idea, fmt):
    msg = client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"ملف الحقائق (المصدر الوحيد للمعلومات الشخصية):\n"
                f"```yaml\n{yaml.dump(facts, allow_unicode=True)}\n```\n\n"
                f"الفكرة: {idea}\n\n"
                f"الصيغة المطلوبة: {FORMAT_SPECS[fmt]}\n\n"
                f"أخرج المحتوى النهائي فقط بدون مقدمات."
            ),
        }],
    )
    return msg.content[0].text.strip()


def append_to_queue(rows):
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    exists = QUEUE.exists()
    with QUEUE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", action="store_true", help="توليد محتوى أسبوع كامل")
    ap.add_argument("--start", help="تاريخ بداية الأسبوع YYYY-MM-DD (افتراضي: الاثنين القادم)")
    args = ap.parse_args()

    cfg = load_config()
    facts = load_facts()
    client = anthropic.Anthropic(api_key=cfg["anthropic"]["api_key"])
    model = cfg["anthropic"].get("model", "claude-sonnet-5")

    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        today = datetime.now()
        start = today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    idea = next_idea()
    print(f"فكرة الأسبوع: {idea}")

    rows, uid = [], int(start.timestamp())
    for day_offset in range(7):
        date = start + timedelta(days=day_offset)
        formats = list(WEEKLY_RHYTHM.get(date.weekday(), []))
        if date.weekday() in DAILY_TWEET_DAYS:
            formats.append("twitter")
        for fmt in formats:
            print(f"  توليد {fmt} ليوم {date:%Y-%m-%d} ...")
            content = generate(client, model, facts, idea, fmt)
            uid += 1
            rows.append({
                "id": uid,
                "date": f"{date:%Y-%m-%d}",
                "time": POST_TIMES.get(fmt, "12:00"),
                "platform": fmt,
                "content": content,
                "media_note": "صمم البصري وفق قالب Canva الموحد" if fmt in ("instagram_carousel", "tiktok_script") else "",
                "status": "draft",
            })

    append_to_queue(rows)
    print(f"\nتمت إضافة {len(rows)} مسودة إلى {QUEUE.relative_to(ROOT)}")
    print("راجعها وعدّلها بصوتك، ثم غيّر status إلى approved لتُنشر في موعدها.")


if __name__ == "__main__":
    main()
