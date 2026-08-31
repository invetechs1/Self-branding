#!/usr/bin/env python3
"""الناشر المجدول — يقرأ queue/queue.csv وينشر ما حان وقته (§38 خطوتا 11-12).

بوابة الاعتماد (§37):
  أحمر  — لا يُنشر إلا بحالة approved كتبها إنسان صراحةً. لا نشر آلي إطلاقاً.
  أصفر  — يتطلب approved (مراجعة بشرية).
  أخضر  — يتطلب approved أيضاً، إلا إذا فُعّل settings.auto_publish_green في config.yml.
النشر عبر الـ APIs الرسمية فقط. المنصات غير المهيأة تُتخطى مع تنبيه.

يُشغَّل كل ساعة عبر GitHub Actions (انظر .github/workflows/publish.yml)
أو يدوياً: python publish.py [--dry-run]
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "automation" / "queue" / "queue.csv"


def publishable(row: dict, settings: dict) -> tuple[bool, str]:
    """§37: من يُسمح بنشره الآن؟"""
    level = (row.get("approval_level") or "yellow").lower()
    status = row.get("status", "")
    if status == "approved":
        return True, ""
    if level == "green" and settings.get("auto_publish_green") and not settings.get("require_approval", True):
        return True, "أخضر — نشر آلي مفعّل"
    return False, f"بانتظار الاعتماد (المستوى: {level})"


def load_config():
    cfg_path = ROOT / "automation" / "config.yml"
    if not cfg_path.exists():
        sys.exit("لا يوجد config.yml — انسخ config.example.yml وعبّئ المفاتيح.")
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


# ── طبقة النشر: دالة لكل منصة — استبدلها بمنصة جدولة خارجية إن أردت ──

def post_twitter(cfg, content):
    import tweepy
    t = cfg.get("twitter", {})
    if not t.get("api_key"):
        return "skip", "X API غير مهيأ"
    client = tweepy.Client(
        consumer_key=t["api_key"], consumer_secret=t["api_secret"],
        access_token=t["access_token"], access_token_secret=t["access_token_secret"],
    )
    reply_to = None
    for part in [p.strip() for p in content.split("\n---\n") if p.strip()]:
        resp = client.create_tweet(text=part, in_reply_to_tweet_id=reply_to)
        reply_to = resp.data["id"]
    return "posted", f"آخر تغريدة: {reply_to}"


def post_instagram(cfg, content):
    # كاروسيل انستقرام يتطلب صوراً مصممة مسبقاً — لا يمكن أتمتته نصياً.
    return "manual", "انشر يدوياً: صمّم الشرائح من النص في العمود content"


def post_tiktok(cfg, content):
    return "manual", "سكربت فيديو — صوّر وانشر يدوياً"


def post_linkedin(cfg, content):
    import requests
    li = cfg.get("linkedin", {})
    if not li.get("access_token"):
        return "skip", "LinkedIn API غير مهيأ"
    r = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={"Authorization": f"Bearer {li['access_token']}",
                 "X-Restli-Protocol-Version": "2.0.0"},
        json={
            "author": li["person_urn"],
            "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content},
                "shareMediaCategory": "NONE"}},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }, timeout=30)
    r.raise_for_status()
    return "posted", r.headers.get("x-restli-id", "")


def post_article(cfg, content):
    # المقالات تُنشر على موقعك — احفظها في site/articles/ وادفعها مع الموقع.
    slug = datetime.now().strftime("%Y-%m-%d-article")
    out = ROOT / "site" / "articles" / f"{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return "posted", f"حُفظ في {out.relative_to(ROOT)} — ادفعه مع الموقع"


PUBLISHERS = {
    "twitter": post_twitter,
    "twitter_thread": post_twitter,
    "instagram_carousel": post_instagram,
    "tiktok_script": post_tiktok,
    "linkedin_post": post_linkedin,
    "article": post_article,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="عرض ما سيُنشر بدون نشر فعلي")
    args = ap.parse_args()

    cfg = load_config()
    tz = ZoneInfo(cfg.get("settings", {}).get("timezone", "Asia/Riyadh"))
    now = datetime.now(tz)

    if not QUEUE.exists():
        print("طابور النشر فارغ.")
        return

    settings = cfg.get("settings", {})
    rows = list(csv.DictReader(QUEUE.open(encoding="utf-8")))
    changed = False

    for row in rows:
        if row["status"] in ("posted", "manual", "skip", "error"):
            continue
        allowed, why = publishable(row, settings)
        if not allowed:
            continue
        due = datetime.strptime(f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        if due > now:
            continue

        if args.dry_run:
            print(f"[dry-run] كان سيُنشر: #{row['id']} {row['platform']} "
                  f"({row.get('approval_level', '?')}) {why}")
            continue

        publisher = PUBLISHERS.get(row["platform"])
        if publisher is None:
            print(f"#{row['id']}: منصة غير معروفة ({row['platform']}) — تُخطّى")
            continue
        try:
            status, note = publisher(cfg, row["content"])
        except Exception as e:  # noqa: BLE001 — فشل منصة واحدة لا يوقف البقية
            status, note = "error", str(e)
        row["status"] = status
        changed = True
        print(f"#{row['id']} {row['platform']}: {status} — {note}")

    if changed:
        with QUEUE.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
