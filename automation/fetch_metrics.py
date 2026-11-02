#!/usr/bin/env python3
"""سحب مقاييس الأداء آلياً — حتى لا يموت محرك التعلّم بالإدخال اليدوي.

يقرأ المنشورات المنشورة من طابور النشر (التي تحمل external_id) ويسأل كل منصة عن
أرقامها، ثم يكتبها في analytics/performance.csv الذي يتغذّى منه feedback.py.

ما تعطيه كل منصة فعلياً:
  X        انطباعات · إعجابات · ردود · إعادة نشر · حفظ (ونقرات وزيارات ملف إن سمح التطبيق)
  تيك توك  مشاهدات · إعجابات · تعليقات · مشاركات
  لينكدإن  إعجابات وتعليقات فقط — انطباعات منشورات الحساب الشخصي غير متاحة عبر الواجهة،
           فتبقى صفراً وتُعلَّم للتعبئة اليدوية (تجدها في «إحصاءات المنشور» داخل التطبيق)

    python automation/fetch_metrics.py              # سحب وتحديث
    python automation/fetch_metrics.py --dry-run    # ماذا سيُسحب ومن أين
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persona import rel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "automation" / "queue" / "queue.csv"
PERF = ROOT / "analytics" / "performance.csv"
CONFIG = ROOT / "automation" / "config.yml"

FIELDS = ["id", "date", "time", "platform", "pillar", "language", "impressions", "likes",
          "comments", "shares", "saves", "profile_visits", "followers_gained", "clicks",
          "hook", "external_id", "captured_at", "source"]

X_PLATFORMS = ("twitter", "twitter_thread")
EMPTY = {k: 0 for k in ("impressions", "likes", "comments", "shares", "saves",
                        "profile_visits", "followers_gained", "clicks")}

# منفذ قابل للاستبدال في الاختبارات دون لمس منطق السحب
X_CLIENT_FACTORY = None


def load_config() -> dict:
    if not CONFIG.exists():
        sys.exit("لا يوجد config.yml — انسخ config.example.yml وعبّئ المفاتيح.")
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def hook_of(content: str, limit: int = 70) -> str:
    """الخطّاف = أول سطر مفيد — يُقاس أثره في تقرير التعلّم."""
    for line in (content or "").splitlines():
        clean = line.strip()
        if len(clean) > 8:
            return clean[:limit]
    return ""


# ───────────────────────────── المنصات ─────────────────────────────

def fetch_x(cfg: dict, ids: list) -> dict:
    """مقاييس تغريدات دفعة واحدة (حتى 100 معرّف لكل نداء)."""
    t = cfg.get("twitter", {})
    if not t.get("api_key") or not ids:
        return {}
    if X_CLIENT_FACTORY:
        client = X_CLIENT_FACTORY(cfg)
    else:
        import tweepy
        client = tweepy.Client(consumer_key=t["api_key"], consumer_secret=t["api_secret"],
                               access_token=t["access_token"],
                               access_token_secret=t["access_token_secret"])

    out = {}
    for batch in (ids[i:i + 100] for i in range(0, len(ids), 100)):
        fields = ["public_metrics", "non_public_metrics"]
        try:
            resp = client.get_tweets(batch, tweet_fields=fields)
        except Exception:        # noqa: BLE001 — المقاييس غير العامة تحتاج صلاحية أعلى
            resp = client.get_tweets(batch, tweet_fields=["public_metrics"])
        for tweet in (getattr(resp, "data", None) or []):
            pm = dict(getattr(tweet, "public_metrics", None) or {})
            npm = dict(getattr(tweet, "non_public_metrics", None) or {})
            out[str(tweet.id)] = {**EMPTY,
                                  "impressions": pm.get("impression_count", 0) or npm.get("impression_count", 0),
                                  "likes": pm.get("like_count", 0),
                                  "comments": pm.get("reply_count", 0),
                                  "shares": pm.get("retweet_count", 0) + pm.get("quote_count", 0),
                                  "saves": pm.get("bookmark_count", 0),
                                  "profile_visits": npm.get("user_profile_clicks", 0),
                                  "clicks": npm.get("url_link_clicks", 0)}
    return out


def fetch_linkedin(cfg: dict, ids: list) -> dict:
    """إعجابات وتعليقات المنشور. الانطباعات غير متاحة لمنشورات الحساب الشخصي."""
    import requests
    li = cfg.get("linkedin", {})
    if not li.get("access_token") or not ids:
        return {}
    base = (li.get("api_base") or "https://api.linkedin.com").rstrip("/")
    headers = {"Authorization": f"Bearer {li['access_token']}",
               "X-Restli-Protocol-Version": "2.0.0"}
    out = {}
    for urn in ids:
        try:
            r = requests.get(f"{base}/v2/socialActions/{urn}", headers=headers, timeout=30)
            r.raise_for_status()
            body = r.json()
        except Exception as e:   # noqa: BLE001 — منشور واحد لا يوقف البقية
            print(f"    تعذّر: {urn[:40]} — {str(e)[:60]}")
            continue
        out[urn] = {**EMPTY,
                    "likes": (body.get("likesSummary") or {}).get("totalLikes", 0),
                    "comments": (body.get("commentsSummary") or {}).get("totalFirstLevelComments", 0)}
    return out


def fetch_tiktok(cfg: dict, ids: list) -> dict:
    import requests
    import tiktok as tk
    t = cfg.get("tiktok", {})
    if not (t.get("access_token") or t.get("refresh_token")) or not ids:
        return {}
    try:
        token = tk._token(cfg)
    except tk.TikTokError as e:
        print(f"    تيك توك: {e}")
        return {}
    url = (f"{tk.api_base(cfg)}/v2/video/query/"
           "?fields=id,like_count,comment_count,share_count,view_count")
    try:
        r = requests.post(url, json={"filters": {"video_ids": ids}},
                          headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/json"}, timeout=60)
        body = r.json()
    except Exception as e:       # noqa: BLE001
        print(f"    تيك توك: تعذّر السحب — {str(e)[:70]}")
        return {}
    out = {}
    for v in ((body.get("data") or {}).get("videos") or []):
        out[str(v.get("id"))] = {**EMPTY,
                                 "impressions": v.get("view_count", 0),
                                 "likes": v.get("like_count", 0),
                                 "comments": v.get("comment_count", 0),
                                 "shares": v.get("share_count", 0)}
    return out


# ───────────────────────────── التجميع ─────────────────────────────

def posted_rows(queue_path: Path = None) -> list:
    path = queue_path or QUEUE
    if not path.exists():
        return []
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    return [r for r in rows if r.get("status") in ("posted", "manual") and r.get("external_id")]


def read_perf(path: Path = None) -> dict:
    path = path or PERF
    if not path.exists():
        return {}
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
             if not ln.lstrip().startswith("#")]
    return {r["id"]: r for r in csv.DictReader(lines) if r.get("id")}


def write_perf(rows: dict, path: Path = None) -> None:
    path = path or PERF
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: (r.get("date", ""), str(r.get("id"))))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def collect(cfg: dict, rows: list) -> tuple[dict, list]:
    """يجمع المقاييس من كل منصة. يعيد (معرّف→مقاييس، تنبيهات)."""
    by_platform: dict = {}
    for r in rows:
        by_platform.setdefault(r["platform"], []).append(r["external_id"])

    metrics, notes = {}, []
    x_ids = [i for p in X_PLATFORMS for i in by_platform.get(p, [])]
    if x_ids:
        print(f"  X: {len(x_ids)} منشوراً ...")
        metrics.update(fetch_x(cfg, x_ids))
    if by_platform.get("linkedin_post"):
        ids = by_platform["linkedin_post"]
        print(f"  لينكدإن: {len(ids)} منشوراً ...")
        got = fetch_linkedin(cfg, ids)
        metrics.update(got)
        if got:
            notes.append("لينكدإن لا يتيح الانطباعات لمنشورات الحساب الشخصي — "
                         "انسخها يدوياً من «إحصاءات المنشور» وإلا تجاهلها محرك التعلّم.")
    if by_platform.get("tiktok_script"):
        ids = by_platform["tiktok_script"]
        print(f"  تيك توك: {len(ids)} فيديو ...")
        metrics.update(fetch_tiktok(cfg, ids))
    return metrics, notes


def merge(rows: list, metrics: dict, existing: dict) -> tuple[dict, int, int]:
    """يدمج المسحوب مع الموجود دون أن يمحو انطباعات عبّأها يحيى يدوياً."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    added = updated = 0
    for r in rows:
        got = metrics.get(r["external_id"])
        if not got:
            continue
        key = str(r["id"])
        prior = existing.get(key, {})
        merged = {**prior, **{k: v for k, v in got.items()},
                  "id": key, "date": r.get("date", ""), "time": r.get("time", ""),
                  "platform": r.get("platform", ""), "pillar": r.get("pillar", ""),
                  "language": r.get("language", ""), "hook": prior.get("hook") or hook_of(r.get("content", "")),
                  "external_id": r["external_id"], "captured_at": now, "source": "api"}
        # رقم يدوي لا تمحوه واجهة لا تعطيه (انطباعات لينكدإن مثلاً)
        for field in ("impressions", "profile_visits", "followers_gained", "clicks"):
            if not got.get(field) and str(prior.get(field) or "0") not in ("", "0"):
                merged[field] = prior[field]
                merged["source"] = "api+manual"
        existing[key] = merged
        updated += key in existing and bool(prior)
        added += not prior
    return existing, added, updated


def main() -> None:
    ap = argparse.ArgumentParser(description="سحب مقاييس الأداء من المنصات")
    ap.add_argument("--dry-run", action="store_true", help="عرض ما سيُسحب بلا كتابة")
    args = ap.parse_args()

    rows = posted_rows()
    if not rows:
        print("لا منشورات منشورة تحمل معرّفاً بعد. انشر أولاً عبر publish.py.")
        return

    counts: dict = {}
    for r in rows:
        counts[r["platform"]] = counts.get(r["platform"], 0) + 1
    print("منشورات قابلة للقياس: " + " · ".join(f"{k}: {v}" for k, v in counts.items()))
    if args.dry_run:
        for r in rows[:15]:
            print(f"  [{r['platform']:14}] {r['external_id'][:34]}  {r.get('date','')}")
        return

    cfg = load_config()
    metrics, notes = collect(cfg, rows)
    if not metrics:
        print("\nلم تُسحب أي مقاييس — تحقق من المفاتيح أو من صلاحيات التطبيقات.")
        return

    merged, added, updated = merge(rows, metrics, read_perf())
    write_perf(merged)
    print(f"\n{rel(PERF)}: أُضيف {added} · حُدِّث {updated}")
    for n in notes:
        print(f"  ⚠ {n}")
    print("الخطوة التالية: python automation/feedback.py --learn")


if __name__ == "__main__":
    main()
