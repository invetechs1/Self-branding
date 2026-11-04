#!/usr/bin/env python3
"""مرصد القرارات الحكومية — يقرأ صفحات أخبار الجهات التي لا تملك RSS.

هذه أثمن مادة لجمهورك: قرار وزاري واحد يمسّ كل مقاول، ولا ينقله أحد بتفسير عملي.

يعمل بمستويين:
  1) محددات CSS صريحة في gov_sources.yml (الأدق — ثبّتها بعد --probe)
  2) استخراج تلقائي حين لا توجد محددات: يبحث عن مجموعة روابط متشابهة البنية
     داخل الصفحة، ويرجّحها بكلمات الجهة المفتاحية

    python automation/gov_watch.py --check            # فحص كل الجهات
    python automation/gov_watch.py --probe hrsd       # اقتراح محددات لجهة
    python automation/gov_watch.py --fetch            # جلب وإضافة إلى سجل الأخبار
    python automation/gov_watch.py --fetch --only hrsd gosi
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persona import Story, _hits, load_persona, normalize, rel, score_story  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "automation" / "gov_sources.yml"
USER_AGENT = ("Mozilla/5.0 (compatible; YahyaBrandEngine/1.0; +personal content research)")
TIMEOUT = 25
MIN_TITLE, MAX_TITLE = 18, 220
DATE_RE = re.compile(r"\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}|\d{4}")


def load_entities() -> dict:
    if not SOURCES.exists():
        sys.exit("لا يوجد automation/gov_sources.yml")
    return (yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}).get("entities", {})


def fetch_html(url: str) -> str:
    """يجلب الصفحة ويفكّ ترميزها بأمان.

    كثير من المواقع العربية لا تذكر charset في ترويسة HTTP بل داخل <meta> فقط،
    وحينها تفترض requests الترميز اللاتيني ISO-8859-1 فيتحول النص العربي إلى رموز
    مشوّهة بصمت — فلا يطابق أي كلمة مفتاحية وتسقط أخبار الجهة كلها.
    """
    import requests
    r = requests.get(url, headers={"User-Agent": USER_AGENT,
                                   "Accept-Language": "ar,en;q=0.8"}, timeout=TIMEOUT)
    r.raise_for_status()
    header = (r.headers.get("Content-Type") or "").lower()
    if "charset" not in header:
        meta = re.search(rb'charset=["\']?([\w-]+)', r.content[:4096], re.I)
        r.encoding = (meta.group(1).decode("ascii", "ignore") if meta
                      else r.apparent_encoding) or "utf-8"
    return r.text


def _soup(html: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _signature(tag) -> str:
    """بصمة بنيوية للرابط: مسار الوالدين وأصنافهم — عناصر القائمة الواحدة تتشابه."""
    parts = []
    node = tag
    for _ in range(3):
        node = node.parent
        if node is None or not getattr(node, "name", None):
            break
        cls = ".".join(sorted(node.get("class", []))[:2])
        parts.append(f"{node.name}{'.' + cls if cls else ''}")
    return ">".join(reversed(parts))


def extract_with_selectors(soup, sel: dict, base_url: str) -> list:
    items = []
    for node in soup.select(sel["item"]):
        title_node = node.select_one(sel["title"]) if sel.get("title") else node
        link_node = node.select_one(sel["link"]) if sel.get("link") else node.find("a")
        date_node = node.select_one(sel["date"]) if sel.get("date") else None
        title = _clean(title_node.get_text() if title_node else "")
        href = (link_node or {}).get("href") if link_node else None
        if not title or not href:
            continue
        items.append({"title": title, "url": urljoin(base_url, href),
                      "date_text": _clean(date_node.get_text()) if date_node else ""})
    return items


def extract_auto(soup, base_url: str, keywords: list) -> tuple[list, str]:
    """استخراج تلقائي: أكبر مجموعة روابط متطابقة البنية وعناوينها معقولة الطول."""
    groups: dict = {}
    for a in soup.find_all("a", href=True):
        title = _clean(a.get_text())
        if not (MIN_TITLE <= len(title) <= MAX_TITLE):
            continue
        href = a["href"]
        if href.startswith(("#", "javascript:", "mailto:")):
            continue
        groups.setdefault(_signature(a), []).append(
            {"title": title, "url": urljoin(base_url, href), "date_text": ""})

    if not groups:
        return [], ""

    def rank(pair):
        sig, rows = pair
        matched = sum(1 for r in rows if _hits(normalize(r["title"]), keywords))
        # مجموعة أكبر + كلمات الجهة حاضرة = قائمة الأخبار على الأرجح
        return (min(len(rows), 40) + matched * 3, len(rows))

    sig, rows = max(groups.items(), key=rank)
    # إزالة التكرار مع الحفاظ على الترتيب
    seen, unique = set(), []
    for r in rows:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        unique.append(r)
    return unique, sig


def entity_items(key: str, entity: dict, html: str | None = None) -> tuple[list, str]:
    html = html if html is not None else fetch_html(entity["url"])
    soup = _soup(html)
    sel = entity.get("selectors") or {}
    if sel.get("item"):
        return extract_with_selectors(soup, sel, entity["url"]), "selectors"
    rows, sig = extract_auto(soup, entity["url"], entity.get("keywords", []))
    return rows, f"auto:{sig}" if sig else "auto"


def to_stories(key: str, entity: dict, rows: list, limit: int = 15) -> list:
    """يحوّل العناصر إلى قصص بمصداقية مصدر حكومي رسمي."""
    now = datetime.now(timezone.utc)
    out = []
    for row in rows[:limit]:
        out.append(Story(
            # الملخص يبقى فارغاً عمداً: حشو اسم الجهة فيه يجعل كل أخبارها متطابقة الدرجة.
            # هوية الجهة محفوظة في source و meta، والتقييم يجري على العنوان وحده.
            title=row["title"],
            summary=row.get("date_text", ""),
            url=row["url"], source=entity["name"], source_type="official_government",
            published=now, lang="ar",
            meta={"kind": "news", "gov_entity": key, "feed_region": "saudi_arabia",
                  "date_text": row.get("date_text", "")}))
    return out


# ───────────────────────────── الأوامر ─────────────────────────────

def cmd_probe(args) -> None:
    entities = load_entities()
    key = args.probe
    if key not in entities:
        sys.exit(f"جهة غير معروفة: {key}. المتاح: {'، '.join(entities)}")
    entity = entities[key]
    print(f"{entity['name']}\n{entity['url']}\n")
    try:
        html = fetch_html(entity["url"])
    except Exception as e:  # noqa: BLE001
        sys.exit(f"تعذّر الوصول: {e}")

    rows, how = entity_items(key, entity, html)
    print(f"طريقة الاستخراج: {how}")
    print(f"عدد العناصر: {len(rows)}\n")
    for r in rows[:8]:
        print(f"  • {r['title'][:95]}")
        print(f"    {r['url'][:100]}")
    if not rows:
        print("  لم يُعثر على قائمة أخبار. افتح الصفحة في المتصفح، وانسخ محدد CSS"
              "\n  لعنصر الخبر الواحد، وضعه في gov_sources.yml ← selectors.item")
        return
    if how.startswith("auto:"):
        print(f"\nالبصمة البنيوية المقترحة: {how[5:]}")
        print("ثبّتها بمحدد CSS صريح في gov_sources.yml لمقاومة تغيّر الموقع.")


def cmd_check(args) -> None:
    entities = load_entities()
    persona = load_persona()
    for key, entity in sorted(entities.items(), key=lambda kv: kv[1].get("priority", 9)):
        try:
            rows, how = entity_items(key, entity)
            n = len(rows)
            relevant = sum(1 for r in rows
                           if _hits(normalize(r["title"]), entity.get("keywords", [])))
            mark = "OK  " if n else "FAIL"
            print(f"{mark} {n:3d} عنصراً ({relevant} ذات صلة) — {entity['name']}  [{how[:28]}]")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL   0 — {entity['name']}\n           السبب: {str(e)[:90]}")


def cmd_fetch(args) -> None:
    import news_engine as NE
    entities = load_entities()
    if args.only:
        entities = {k: v for k, v in entities.items() if k in args.only}
    persona, now = load_persona(), datetime.now(timezone.utc)

    stored = NE.load_stored()
    seen = {s.url for s in stored if s.url}
    fresh, failures = [], []

    for key, entity in sorted(entities.items(), key=lambda kv: kv[1].get("priority", 9)):
        try:
            rows, how = entity_items(key, entity)
        except Exception as e:  # noqa: BLE001 — جهة معطّلة لا توقف البقية
            failures.append((entity["name"], str(e)[:70]))
            continue
        stories = [s for s in to_stories(key, entity, rows) if s.url not in seen]
        for s in stories:
            score_story(s, persona, now)
        kept = [s for s in stories if s.scores["total"] >= persona["thresholds"]["pipeline_entry"]]
        fresh += kept
        print(f"  {entity['name']}: {len(rows)} عنصراً، جديد ومؤهل: {len(kept)}")

    if failures:
        print("\nجهات تعذّر الوصول إليها:")
        for name, why in failures:
            print(f"  ✗ {name} — {why}")

    if not fresh:
        print("\nلا جديد مؤهل من الجهات الحكومية.")
        return

    NE.save_stories(stored + fresh)
    print(f"\nأُضيف {len(fresh)} خبراً حكومياً إلى {rel(NE.NEWS_FILE)}")
    for s in sorted(fresh, key=lambda s: -s.scores["total"])[:8]:
        print(f"  [{s.scores['total']:5.1f}] {s.title[:85]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="مرصد أخبار الجهات الحكومية")
    ap.add_argument("--check", action="store_true", help="فحص كل الجهات")
    ap.add_argument("--probe", metavar="KEY", help="اقتراح محددات لجهة واحدة")
    ap.add_argument("--fetch", action="store_true", help="جلب الأخبار وإضافتها للسجل")
    ap.add_argument("--only", nargs="+", help="حصر الجلب بجهات محددة")
    args = ap.parse_args()

    if args.probe:
        cmd_probe(args)
    elif args.check:
        cmd_check(args)
    elif args.fetch:
        cmd_fetch(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
