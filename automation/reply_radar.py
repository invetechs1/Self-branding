#!/usr/bin/env python3
"""رادار الردود — أين يستحق صوتك أن يظهر اليوم.

الرد الذكي على منشور رائج في قطاعك يصل أحياناً أكثر من منشور كامل على حسابك.
هذا الرادار يرشّح المنشورات التي تستحق ردك ويعطيك زاوية الرد — وتكتبه أنت.

⚠️ لا يرد ولا ينشر. لا توجد في هذا الملف دالة إرسال رد، وهذا ضمان بنيوي:
   الرد الآلي مخالف لشروط المنصات، والرد المُصطنع يُكتشف ويضرّ السمعة التي نبنيها.

    python automation/reply_radar.py                 # قائمة اليوم
    python automation/reply_radar.py --mark 1 3 5    # تعليم ما رددتَ عليه
    python automation/reply_radar.py --dry-run       # ماذا سيُبحث عنه
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persona import Story, _hits, activity_hits, load_persona, normalize, rel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "content" / "reply-watchlist.yml"
SEEN = ROOT / "automation" / "queue" / "replied.jsonl"
REPORT = ROOT / "analytics" / "reply-radar.md"
CONFIG = ROOT / "automation" / "config.yml"

X_CLIENT_FACTORY = None          # منفذ قابل للاستبدال في الاختبارات


def load_watchlist() -> dict:
    if not WATCHLIST.exists():
        return {"search_terms": [], "accounts": {}, "rules": {}}
    return yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}


def load_config() -> dict:
    if not CONFIG.exists():
        sys.exit("لا يوجد config.yml — انسخ config.example.yml وعبّئ مفاتيح X.")
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def load_seen() -> set:
    if not SEEN.exists():
        return set()
    out = set()
    for line in SEEN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.add(str(json.loads(line)["id"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return out


def mark_seen(ids: list, note: str = "replied") -> None:
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    with SEEN.open("a", encoding="utf-8") as f:
        for i in ids:
            f.write(json.dumps({"id": str(i), "note": note,
                                "at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                               ensure_ascii=False) + "\n")


# ───────────────────────────── الترشيح ─────────────────────────────

def velocity(metrics: dict, age_hours: float) -> float:
    """سرعة التفاعل: منشور يصعد الآن يستحق رداً مبكراً أكثر من منشور هدأ."""
    total = (metrics.get("like_count", 0) + 2 * metrics.get("reply_count", 0)
             + 2 * metrics.get("retweet_count", 0) + metrics.get("quote_count", 0))
    return total / max(0.5, age_hours)


def is_safe(text: str, persona: dict) -> tuple[bool, str]:
    """تجاوز الجدلي والسياسي والشخصي — الرد هناك خسارة صافية."""
    safety = persona["safety"]
    hits = _hits(normalize(text), safety.get("red_flag_terms", []))
    if hits:
        return False, f"موضوع حساس ({', '.join(map(str, hits[:2]))})"
    return True, ""


def angle_for(activities: list, persona: dict) -> str:
    """زاوية الرد المقترحة — من خبرتك لا من رأي عام."""
    suggestions = {
        "contracting_projects": "أضف رقماً أو تجربة تنفيذية: ما الذي يحدث فعلاً في الموقع؟",
        "government_decisions": "ترجم القرار عملياً: من يتأثر، ومتى، وماذا يفعل المقاول غداً؟",
        "site_quality": "اذكر السبب الهندسي الحقيقي وراء العيب، لا الوصف العام",
        "ai_technology": "اربطه بالإنشاءات السعودية: أين يفيد فعلاً وأين لا يزال وعداً؟",
        "real_estate": "أضف منظور المطوّر: الجدوى والتدفق النقدي لا السعر وحده",
        "saudi_trends": "اربط الترند بقطاعك إن كان الربط حقيقياً، وإلا تجاهله",
        "official_occasions": "زاوية مهنية لا تهنئة",
    }
    for key in activities:
        if key in suggestions:
            return suggestions[key]
    return "أضف ما لا يعرفه غيرك: رقم، أو خطأ شائع، أو نتيجة من التنفيذ"


def score_candidate(item: dict, persona: dict, now: datetime) -> dict:
    """يرتّب المنشور حسب: تقاطعه مع أنشطتك × سرعة تفاعله × حداثته."""
    # نفس منطق الأنشطة المستخدم في ترتيب الأخبار: مرتّب بقوة التطابق × وزن النشاط،
    # فتأتي الزاوية من الموضوع الغالب لا من ترتيب الإعدادات
    acts = activity_hits(Story(title=item["text"]), persona)
    activities = [a["key"] for a in acts]

    age = max(0.1, (now - item["created_at"]).total_seconds() / 3600)
    v = velocity(item.get("metrics", {}), age)
    relevance = min(1.0, len(activities) / 2)
    freshness = max(0.0, 1 - age / 12)
    item.update({"activities": activities, "age_hours": round(age, 1),
                 "velocity": round(v, 1),
                 "score": round(100 * (0.5 * relevance + 0.3 * min(1.0, v / 40) + 0.2 * freshness), 1),
                 "angle": angle_for(activities, persona)})
    return item


def fetch_x_candidates(cfg: dict, terms: list, accounts: list, limit: int = 60) -> list:
    """منشورات حديثة من البحث ومن حسابات المتابعة."""
    t = cfg.get("twitter", {})
    if not t.get("api_key"):
        return []
    if X_CLIENT_FACTORY:
        client = X_CLIENT_FACTORY(cfg)
    else:
        import tweepy
        client = tweepy.Client(consumer_key=t["api_key"], consumer_secret=t["api_secret"],
                               access_token=t["access_token"],
                               access_token_secret=t["access_token_secret"])

    query_terms = " OR ".join(f'"{x}"' for x in terms[:10])
    query = f"({query_terms}) -is:retweet -is:reply lang:ar" if query_terms else ""
    if accounts:
        query = (f"({' OR '.join('from:' + a for a in accounts[:20])}) -is:retweet"
                 if not query else query)
    if not query:
        return []

    try:
        resp = client.search_recent_tweets(
            query=query, max_results=min(limit, 100),
            tweet_fields=["created_at", "public_metrics", "author_id", "lang"])
    except Exception as e:      # noqa: BLE001
        print(f"  تعذّر البحث في X: {str(e)[:90]}")
        return []

    out = []
    for tw in (getattr(resp, "data", None) or []):
        created = getattr(tw, "created_at", None) or datetime.now(timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        out.append({"id": str(tw.id), "text": tw.text or "",
                    "author_id": str(getattr(tw, "author_id", "")),
                    "created_at": created,
                    "metrics": dict(getattr(tw, "public_metrics", None) or {}),
                    "url": f"https://x.com/i/web/status/{tw.id}"})
    return out


def shortlist(items: list, persona: dict, rules: dict, seen: set,
              now: datetime | None = None) -> tuple[list, list]:
    """يعيد (المرشحون، أسباب الاستبعاد)."""
    now = now or datetime.now(timezone.utc)
    max_age = float(rules.get("max_age_hours", 6))
    min_eng = int(rules.get("min_engagement", 5))
    cap = int(rules.get("max_suggestions_per_day", 10))

    kept, dropped = [], []
    for item in items:
        if rules.get("skip_if_replied", True) and item["id"] in seen:
            dropped.append((item, "سبق أن رددتَ عليه"))
            continue
        scored = score_candidate(dict(item), persona, now)
        if scored["age_hours"] > max_age:
            dropped.append((scored, f"مضى عليه {scored['age_hours']:.0f} ساعة"))
            continue
        engagement = sum(scored.get("metrics", {}).get(k, 0)
                         for k in ("like_count", "reply_count", "retweet_count"))
        if engagement < min_eng:
            dropped.append((scored, "تفاعل ضعيف — لا أحد يراه"))
            continue
        if not scored["activities"]:
            dropped.append((scored, "خارج أنشطتك الستة"))
            continue
        if rules.get("avoid_controversy", True):
            ok, why = is_safe(scored["text"], persona)
            if not ok:
                dropped.append((scored, why))
                continue
        kept.append(scored)

    kept.sort(key=lambda x: -x["score"])
    return kept[:cap], dropped


def build_report(kept: list, dropped: list, persona: dict) -> str:
    labels = {k: v.get("label_ar", k) for k, v in (persona.get("saudi_activities") or {}).items()}
    lines = [f"# رادار الردود — {datetime.now():%Y-%m-%d}", "",
             f"مرشحون اليوم: **{len(kept)}** · مستبعد: {len(dropped)}", "",
             "> النظام يقترح ولا يرد. اكتب ردك بنفسك — الرد المُصطنع يُكتشف.", ""]
    for i, item in enumerate(kept, 1):
        acts = "، ".join(labels.get(a, a) for a in item["activities"])
        lines += [f"## {i}. [{item['score']:.0f}] {acts}",
                  f"{item['text'][:240].strip()}",
                  "",
                  f"- الرابط: {item['url']}",
                  f"- العمر: {item['age_hours']:.1f} ساعة · سرعة التفاعل: {item['velocity']}",
                  f"- **زاوية ردك:** {item['angle']}", ""]
    if not kept:
        lines.append("لا مرشح اليوم. وسّع `search_terms` أو املأ `accounts` في "
                     "`content/reply-watchlist.yml`.")
    if dropped:
        lines += ["---", "", "### مستبعدون وأسبابهم", ""]
        lines += [f"- {w} — {it['text'][:70].strip()}" for it, w in dropped[:10]]
    lines += ["", "---",
              "*بعد الرد: `python automation/reply_radar.py --mark <الأرقام>` "
              "حتى لا تتكرر الاقتراحات.*"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="رادار الردود — اقتراح لا نشر")
    ap.add_argument("--mark", nargs="+", metavar="ID", help="تعليم منشورات رددتَ عليها")
    ap.add_argument("--dry-run", action="store_true", help="عرض ما سيُبحث عنه")
    args = ap.parse_args()

    watch = load_watchlist()
    rules = watch.get("rules") or {}
    terms = watch.get("search_terms") or []
    accounts = [a for group in (watch.get("accounts") or {}).values() for a in (group or [])]

    if args.mark:
        mark_seen(args.mark)
        print(f"عُلّم {len(args.mark)} منشوراً كمردود عليه.")
        return

    if args.dry_run:
        print(f"كلمات البحث ({len(terms)}): {'، '.join(terms[:8])}")
        print(f"حسابات المتابعة: {len(accounts)}")
        print(f"الضوابط: أقصى عمر {rules.get('max_age_hours', 6)} ساعات · "
              f"حد أدنى للتفاعل {rules.get('min_engagement', 5)} · "
              f"أقصى اقتراحات {rules.get('max_suggestions_per_day', 10)}")
        return

    persona = load_persona()
    items = fetch_x_candidates(load_config(), terms, accounts)
    if not items:
        print("لا منشورات — تحقق من مفاتيح X أو وسّع كلمات البحث.")
        return

    kept, dropped = shortlist(items, persona, rules, load_seen())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(kept, dropped, persona), encoding="utf-8")
    print(f"الرادار: {rel(REPORT)} — {len(kept)} مرشحاً من {len(items)}")
    for i, item in enumerate(kept[:5], 1):
        print(f"  {i}. [{item['score']:.0f}] {item['text'][:70].strip()}")


if __name__ == "__main__":
    main()
