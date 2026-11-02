#!/usr/bin/env python3
"""اختبار النظام كاملاً من الطرف إلى الطرف — بلا شبكة خارجية وبلا مفاتيح API.

يشغّل المسار الحقيقي: خادم RSS محلي → جلب فعلي بـ feedparser → ترتيب → تجميع المكرر →
ثقة الحقائق → توليد (بنموذج بديل) → بوابة الاعتماد → النشر التجريبي → التعلّم → التقرير.

ما هو حقيقي هنا: كل منطق النظام (الجلب، الترتيب، التجميع، السلامة، الطابور، النشر، التعلّم).
ما هو بديل: استدعاء Claude API فقط (لا مفتاح في بيئة الاختبار)، ومصادر الأخبار (ملفات ثابتة
في fixtures/ تُقدَّم عبر 127.0.0.1) — لأن المحتوى الثابت وحده يجعل النتيجة قابلة للتكرار.

    python automation/tests/run_tests.py            # تشغيل كل الاختبارات
    python automation/tests/run_tests.py --verbose  # مع تفاصيل كل خطوة
"""

from __future__ import annotations

import argparse
import csv
import http.server
import json
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import types
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

AUTOMATION = Path(__file__).resolve().parent.parent
ROOT = AUTOMATION.parent
sys.path.insert(0, str(AUTOMATION))

import yaml  # noqa: E402

import persona as P  # noqa: E402
import news_engine as NE  # noqa: E402

RESULTS: list = []
VERBOSE = False


def check(label: str, condition: bool, detail: str = "") -> bool:
    RESULTS.append((label, bool(condition), detail))
    mark = "\033[32m PASS \033[0m" if condition else "\033[31m FAIL \033[0m"
    print(f"  [{mark}] {label}" + (f"  — {detail}" if detail and (VERBOSE or not condition) else ""))
    return bool(condition)


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


# ───────────────────────── خادم التغذيات المحلي ─────────────────────────

class FeedServer:
    """يقدّم ملفات fixtures عبر HTTP محلي — ليمر الجلب بمسار feedparser الحقيقي."""

    def __init__(self, directory: Path):
        handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(  # noqa: E731
            *a, directory=str(directory), **kw)
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.httpd.allow_reuse_address = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class TikTokMock:
    """يحاكي Content Posting API: init → رابط رفع → PUT → حالة النشر."""

    def __init__(self):
        self.calls: list = []
        self.uploaded = b""
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, body):
                raw = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_PUT(self):            # رفع بايتات الفيديو
                n = int(self.headers.get("Content-Length", 0))
                outer.uploaded += self.rfile.read(n)
                outer.calls.append(("PUT", self.path, self.headers.get("Content-Range")))
                self.send_response(201)
                self.end_headers()

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(n).decode() if n else ""
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    body = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
                outer.calls.append(("POST", self.path, body,
                                    self.headers.get("Authorization", "")))
                ok = {"code": "ok", "message": "", "log_id": "test"}
                if self.path.endswith("/oauth/token/"):
                    self._json(200, {"access_token": "NEW_ACCESS", "refresh_token": "NEW_REFRESH",
                                     "expires_in": 86400, "scope": "video.upload"})
                elif self.path.endswith("/creator_info/query/"):
                    self._json(200, {"data": {"creator_username": "yahya",
                                              "max_video_post_duration_sec": 600,
                                              "privacy_level_options": ["SELF_ONLY", "PUBLIC_TO_EVERYONE"]},
                                     "error": ok})
                elif self.path.endswith("/video/init/"):
                    self._json(200, {"data": {"publish_id": "v_pub_7788",
                                              "upload_url": f"{outer.base}/upload/7788"},
                                     "error": ok})
                elif self.path.endswith("/status/fetch/"):
                    self._json(200, {"data": {"status": "PUBLISH_COMPLETE"}, "error": ok})
                else:
                    self._json(404, {"error": {"code": "not_found", "message": self.path}})

        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), H)
        self.httpd.allow_reuse_address = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def paths(self) -> list:
        return [c[1] for c in self.calls]

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def render_fixtures(dest: Path) -> None:
    """يستبدل تواريخ العناصر بتواريخ نسبية للآن، ليعمل مكوّن الحداثة فعلياً."""
    now = datetime.now(timezone.utc)
    src = Path(__file__).resolve().parent / "fixtures"
    dest.mkdir(parents=True, exist_ok=True)
    for xml in src.glob("*.xml"):
        text = xml.read_text(encoding="utf-8")
        for hours in re.findall(r"\{\{DATE_(\d+)H\}\}", text):
            stamp = format_datetime(now - timedelta(hours=int(hours)))
            text = text.replace(f"{{{{DATE_{hours}H}}}}", stamp)
        (dest / xml.name).write_text(text, encoding="utf-8")


# ───────────────────────── نموذج لغوي بديل ─────────────────────────

class StubAnthropic:
    """يحاكي Claude API: يعيد نصاً مبنياً على الطلب الفعلي، ويسجّل كل استدعاء."""

    calls: list = []

    class _Messages:
        def create(self, **kw):
            StubAnthropic.calls.append(kw)
            prompt = kw["messages"][0]["content"]
            title = re.search(r"^العنوان: (.+)$", prompt, re.M)
            headline = title.group(1) if title else "فكرة من بنك الأفكار"
            body = (f"{headline[:70]} — تطور يستحق الانتباه.\n\n"
                    "ما يعنيه للسوق السعودي: المقاولون الذين يملكون بياناتهم الميدانية سيستفيدون "
                    "أولاً، ومن لا يملكها سيدفع الفرق تأخيراً وتكلفة.\n\n"
                    "السؤال العملي: كم يكلفك اليوم ألا تعرف نسبة الإنجاز الحقيقية؟")
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=body)])

    def __init__(self, **kw):
        self.messages = self._Messages()


# ───────────────────────── الاختبارات ─────────────────────────

def test_persona_logic() -> None:
    section("1) منطق الشخصية: الترتيب والتجميع والسلامة")
    persona = P.load_persona()
    now = datetime.now(timezone.utc)

    relevant = P.score_story(P.Story(
        title="Saudi Arabia mandates BIM for government infrastructure projects",
        summary="Requirement affects contractors and engineering consultancies under Vision 2030.",
        source="wire", source_type="official_government", published=now), persona, now)
    noise = P.score_story(P.Story(
        title="Local cafe launches new seasonal drink", summary="Limited edition beverage.",
        source="blog", source_type="unknown_website", published=now), persona, now)

    check("قصة ذات صلة تتجاوز عتبة خط الإنتاج", relevant.scores["total"] >= persona["thresholds"]["pipeline_entry"],
          f"{relevant.scores['total']}")
    check("قصة غير ذات صلة تبقى دون العتبة", noise.scores["total"] < persona["thresholds"]["pipeline_entry"],
          f"{noise.scores['total']}")
    check("المرادفات تعمل (AI ≡ Artificial Intelligence)",
          P.score_story(P.Story(title="AI agents reach enterprise ERP", source_type="industry_publication",
                                published=now), persona, now).scores["personal_interest"] > 0)
    check("الأولوية الجغرافية ترصد السعودية", relevant.meta["region"] == "saudi_arabia")
    check("الحداثة تتناقص مع الزمن",
          P.freshness_score(P.Story(title="x", published=now - timedelta(hours=48)), persona, now)
          < P.freshness_score(P.Story(title="x", published=now - timedelta(hours=2)), persona, now))
    check("الخبر القديم جداً يسقط إلى صفر",
          P.freshness_score(P.Story(title="x", published=now - timedelta(days=30)), persona, now) == 0.0)

    green = P.classify_approval("شرح مبسط لتقنية التوأم الرقمي في مشاريع البنية التحتية", persona, 0.95)
    yellow = P.classify_approval("أتوقع أن تصبح مراقبة المواقع بالرؤية الحاسوبية معياراً خلال ثلاث سنوات", persona, 0.95)
    red_money = P.classify_approval("إيرادات الشركة وأرباحها الفصلية بلغت", persona, 0.95)
    red_claim = P.classify_approval("طبقنا هذا النظام في شركتي وحققنا نتائج", persona, 0.95)
    red_conf = P.classify_approval("خبر من مصدر واحد مجهول", persona, 0.35)
    check("محتوى تعليمي موثّق ← أخضر", green[0] == "green", str(green))
    check("توقع ← أصفر", yellow[0] == "yellow", str(yellow))
    check("مصطلح مالي حساس ← أحمر", red_money[0] == "red", str(red_money))
    check("ادعاء تجربة شخصية غير موثّقة ← أحمر", red_claim[0] == "red", str(red_claim))
    check("ثقة حقائق متدنية ← أحمر", red_conf[0] == "red", str(red_conf))

    check("إعادة الصياغة تُكتشف كتكرار",
          P.similarity("PIF-backed startup raises $40 million for AI construction monitoring in Riyadh",
                       "PIF backs AI construction monitoring startup in Riyadh with $40m round") >= 0.55)
    check("قصتان مختلفتان لا تُدمجان",
          P.similarity("Saudi Arabia mandates BIM for infrastructure",
                       "Local cafe launches new seasonal drink") < 0.55)
    check("مزيج المحتوى يرتّب العمود الأنقص أولاً",
          P.mix_deficit({"ai_technology": 12}, persona)[0] != "ai_technology")
    check("تعليمات النموذج تحمل قواعد السلامة",
          all(k in P.build_system_prompt(persona, P.load_facts()) for k in ("§33", "§34", "§36")))


def test_discovery(tmp: Path, server: FeedServer) -> list:
    section("2) الاكتشاف: جلب RSS حقيقي → ترتيب → تجميع → ثقة الحقائق")
    persona = P.load_persona()
    sources = {"feeds": [
        {"name": "Saudi Official Wire", "url": f"{server.base}/saudi_official.xml",
         "type": "official_government", "region": "saudi_arabia"},
        {"name": "ConTech Weekly", "url": f"{server.base}/contech_trade.xml",
         "type": "industry_publication", "region": "gcc"},
        {"name": "Global Tech Daily", "url": f"{server.base}/global_tech.xml",
         "type": "major_international_publication", "region": "global"},
    ]}
    (tmp / "sources.yml").write_text(yaml.dump(sources, allow_unicode=True), encoding="utf-8")
    NE.SOURCES = tmp / "sources.yml"
    NE.NEWS_FILE = tmp / "news.jsonl"
    NE.REPORT_DIR = tmp / "intelligence"

    fetched = NE.fetch_feeds(limit_per_feed=25)
    check("جلب فعلي من 3 مصادر عبر feedparser", len(fetched) == 10, f"{len(fetched)} عنصراً")
    check("العناوين والتواريخ قُرئت", all(s.title and s.published for s in fetched))

    now = datetime.now(timezone.utc)
    for s in fetched:
        P.score_story(s, persona, now)
        s.meta["opportunities"] = NE.detect_opportunities(s)
    kept = [s for s in fetched if s.scores["total"] >= persona["thresholds"]["pipeline_entry"]]
    dropped = [s for s in fetched if s not in kept]

    check("الضجيج استُبعد (المقهى والإجازات)",
          all(not any(w in s.title.lower() for w in ("cafe", "holiday")) for s in kept),
          f"استُبعد {len(dropped)}")
    ranked = sorted(kept, key=lambda s: -s.scores["total"])
    check("قصتا السعودية/الإنشاءات تتصدران الترتيب",
          all(any(w in s.title.lower() for w in ("bim", "construction")) for s in ranked[:2]),
          " | ".join(f"{s.scores['total']:.0f} {s.title[:42]}" for s in ranked[:2]))
    check("الضجيج في ذيل الترتيب",
          all(s.scores["total"] < ranked[len(ranked) // 2].scores["total"]
              for s in fetched if "cafe" in s.title.lower()))

    NE.save_stories(kept)
    reloaded = NE.load_stored()
    check("التخزين والاسترجاع بلا فقد", len(reloaded) == len(kept) and
          reloaded[0].scores["total"] == kept[0].scores["total"])

    clusters = NE.cluster_stories(reloaded, persona)
    merged = [c for c in clusters if c["source_count"] > 1]
    check("الروايتان لنفس التمويل اندمجتا في عنقود واحد", len(merged) == 1,
          f"{len(clusters)} عنقوداً، أكبرها {max(c['source_count'] for c in clusters)} مصادر")
    check("العنقود متعدد المصادر يرفع ثقة الحقائق",
          merged[0]["fact_confidence"] > min(c["fact_confidence"] for c in clusters) if merged else False)
    check("المصدر الحكومي يحقق ثقة مؤهلة للأخضر",
          max(c["fact_confidence"] for c in clusters) >= persona["thresholds"]["fact_confidence_autopublish"])

    opportunities = [o for c in clusters for o in c["primary"].meta.get("opportunities", [])]
    check("رُصدت فرص أعمال (§45)", len(opportunities) >= 2,
          ", ".join(sorted({o["label"] for o in opportunities})))
    return clusters


def test_generation(tmp: Path) -> Path:
    section("3) التوليد: عنقود خبر → منشور موسوم ببوابة الاعتماد")
    sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda **kw: StubAnthropic())
    import generate_posts as G

    G.QUEUE = tmp / "queue.csv"
    cfg = tmp / "config.yml"
    cfg.write_text('anthropic: {api_key: "stub", model: "claude-sonnet-5"}\n'
                   'settings: {timezone: "Asia/Riyadh", require_approval: true, default_language: "ar"}\n'
                   'news: {posts_per_run: 3, platforms: ["linkedin_post", "twitter"]}\n', encoding="utf-8")
    G.load_config = lambda: yaml.safe_load(cfg.read_text(encoding="utf-8"))

    old_argv = sys.argv
    sys.argv = ["generate_posts.py", "--from-news"]
    try:
        G.main()
    finally:
        sys.argv = old_argv

    rows = list(csv.DictReader(G.QUEUE.open(encoding="utf-8")))
    check("المسودات أُنشئت", len(rows) == 6, f"{len(rows)} مسودة (3 قصص × منصتان)")
    check("مخطط الطابور كامل", list(rows[0].keys()) == G.QUEUE_FIELDS)
    check("كل مسودة موسومة بعمود ولغة ومستوى اعتماد",
          all(r["pillar"] and r["language"] and r["approval_level"] in ("green", "yellow", "red") for r in rows))
    check("كل مسودة مرتبطة بمصدرها ودرجتها",
          all(r["source_url"].startswith("http") and float(r["relevance"]) > 0 for r in rows))
    check("لا شيء يبدأ معتمداً", all(r["status"] == "draft" for r in rows))
    check("قصة واحدة لا تُستهلك مرتين", len({r["source_url"] for r in rows}) == 3)
    check("التكرار بين المنصات يُرصد (§43)",
          any("يشبه منشوراً سابقاً" in r["review_notes"] for r in rows))
    check("ملف الحقائق وصل إلى النموذج",
          all("ملف الحقائق" in c["messages"][0]["content"] for c in StubAnthropic.calls))
    check("دليل المنصة وصل إلى النموذج",
          any("لينكدإن" in c["messages"][0]["content"] or "150-500" in c["messages"][0]["content"]
              for c in StubAnthropic.calls))

    # تشغيل ثانٍ: لا يعيد استخدام القصص نفسها
    before = len(rows)
    sys.argv = ["generate_posts.py", "--from-news"]
    try:
        G.main()
        rows2 = list(csv.DictReader(G.QUEUE.open(encoding="utf-8")))
        grew = len(rows2) > before
    except SystemExit as e:
        grew, rows2 = False, rows
        check("تشغيل ثانٍ يتوقف بدل تكرار القصص", "استُخدمت في محتوى سابق" in str(e), str(e)[:60])
    finally:
        sys.argv = old_argv
    if grew:
        check("التشغيل الثاني يستخدم قصصاً جديدة فقط",
              len({r["source_url"] for r in rows2}) > 3)
    return G.QUEUE


def test_publish_gate(tmp: Path, queue: Path) -> None:
    section("4) بوابة النشر: لا شيء يخرج دون اعتماد، والأحمر لا يخرج آلياً")
    import publish

    strict = {"require_approval": True, "auto_publish_green": False}
    relaxed = {"require_approval": False, "auto_publish_green": True}
    row = lambda level, status: {"approval_level": level, "status": status}  # noqa: E731

    check("مسودة خضراء لا تُنشر في الوضع الافتراضي", not publish.publishable(row("green", "draft"), strict)[0])
    check("مسودة صفراء لا تُنشر", not publish.publishable(row("yellow", "draft"), strict)[0])
    check("مسودة حمراء لا تُنشر", not publish.publishable(row("red", "draft"), strict)[0])
    check("الأحمر لا يُنشر حتى مع تفعيل النشر الآلي",
          not publish.publishable(row("red", "draft"), relaxed)[0])
    check("الأصفر لا يُنشر حتى مع تفعيل النشر الآلي",
          not publish.publishable(row("yellow", "draft"), relaxed)[0])
    check("الأخضر يُنشر آلياً عند تفعيل الإعداد صراحةً", publish.publishable(row("green", "draft"), relaxed)[0])
    check("الاعتماد البشري يسمح بنشر أي مستوى",
          all(publish.publishable(row(lv, "approved"), strict)[0] for lv in ("green", "yellow", "red")))
    check("المنشور سابقاً لا يُعاد نشره",
          not publish.publishable(row("green", "posted"), relaxed)[0])
    check("المرفوض لا يُنشر", not publish.publishable(row("green", "rejected"), relaxed)[0])
    check("الفاشل سابقاً لا يُعاد تلقائياً", not publish.publishable(row("green", "error"), relaxed)[0])

    # تشغيل الناشر فعلياً على طابور معتمد (dry-run) — يثبت أن المسار كامل يعمل
    rows = list(csv.DictReader(queue.open(encoding="utf-8")))
    rows[0]["status"], rows[0]["date"] = "approved", "2020-01-01"
    with queue.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    publish.QUEUE = queue
    cfg = tmp / "config.yml"
    publish.load_config = lambda: yaml.safe_load(cfg.read_text(encoding="utf-8"))
    old_argv = sys.argv
    sys.argv = ["publish.py", "--dry-run"]
    try:
        publish.main()
        check("الناشر يعمل على طابور حقيقي (تشغيل تجريبي)", True)
    except Exception as e:  # noqa: BLE001
        check("الناشر يعمل على طابور حقيقي (تشغيل تجريبي)", False, str(e)[:80])
    finally:
        sys.argv = old_argv


def test_learning(tmp: Path, queue: Path) -> None:
    section("5) التعلّم: الأداء وقرارات الاعتماد تعيد ضبط الأوزان")
    import feedback as F

    perf = tmp / "performance.csv"
    fields = ["id", "date", "time", "platform", "pillar", "language", "impressions", "likes",
              "comments", "shares", "saves", "profile_visits", "followers_gained", "clicks", "hook"]
    rows = []
    # الإنشاءات تتفوق، العقار يضعف — بعيّنات كافية لتجاوز حد التعلّم
    for pillar, rate, n in (("construction_projects", 0.09, 5), ("ai_technology", 0.04, 5),
                            ("real_estate", 0.012, 4)):
        for i in range(n):
            likes = 5000 * rate * 0.5
            rows.append({"id": f"{pillar}{i}", "date": "2026-09-0%d" % (i + 1), "time": "08:30",
                         "platform": "linkedin_post", "pillar": pillar, "language": "ar",
                         "impressions": 5000, "likes": round(likes), "comments": round(likes * .1),
                         "shares": round(likes * .08), "saves": round(likes * .05),
                         "profile_visits": round(likes * .3), "followers_gained": round(likes * .05),
                         "clicks": 10, "hook": "h"})
    with perf.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    F.PERF, F.QUEUE = perf, queue
    F.WEIGHTS, F.REPORT = tmp / "weights.yml", tmp / "learning-report.md"
    F.learn(None)

    weights = yaml.safe_load(F.WEIGHTS.read_text(encoding="utf-8"))["pillar_multipliers"]
    check("وزن العمود الناجح ارتفع", weights["construction_projects"] > 1.0,
          f"{weights['construction_projects']}×")
    check("وزن العمود الضعيف انخفض", weights["real_estate"] < 1.0, f"{weights['real_estate']}×")
    check("العمود بلا بيانات يبقى محايداً", weights["occasions"] == 1.0)
    check("المضاعِف محصور ضمن الحدود",
          all(F.BOUNDS[0] <= v <= F.BOUNDS[1] for v in weights.values()))
    check("تقرير التعلّم يشرح سبب كل وزن", "أداء" in F.REPORT.read_text(encoding="utf-8"))

    # الأثر الفعلي: الوزن الجديد يغيّر ترتيب الأخبار
    persona, now = P.load_persona(), datetime.now(timezone.utc)
    # قصة متوسطة الدرجة (لا تبلغ السقف) ليظهر أثر الوزن المتعلَّم
    story = P.Story(title="مقاولون يتبنون نماذج BIM في مشاريع البنية التحتية",
                    summary="دراسة إنتاجية.", source_type="social_media",
                    published=now - timedelta(hours=60))
    before = P.score_story(P.Story(**{**story.__dict__, "scores": {}, "meta": {}}), persona, now, {}).scores["total"]
    after = P.score_story(P.Story(**{**story.__dict__, "scores": {}, "meta": {}}), persona, now, weights).scores["total"]
    check("الوزن المتعلَّم يرفع ترتيب القصة فعلياً", after > before, f"{before} ← {after}")


def test_weekly_report(tmp: Path) -> None:
    section("6) التقرير الأسبوعي (§47)")
    old_argv = sys.argv
    sys.argv = ["news_engine.py", "--report"]
    try:
        NE.weekly_report(argparse.Namespace())
    finally:
        sys.argv = old_argv
    reports = list((tmp / "intelligence").glob("*.md"))
    check("التقرير وُلّد", len(reports) == 1)
    text = reports[0].read_text(encoding="utf-8") if reports else ""
    for heading in ("أهم 10 تطورات", "فرص محتوى", "فرص أعمال", "الاتجاهات المرصودة",
                    "التقنية", "المقاولات والمشاريع", "الفرصة السعودية", "القرارات الحكومية", "الموضوع المقترح للتعمّق"):
        check(f"بند التقرير: {heading}", heading in text)


def test_tiktok(tmp: Path) -> None:
    section("8) تيك توك: الكابشن، ورفع الفيديو، وتجديد الرمز")
    import tiktok as tk
    import publish

    check("الكابشن يُقرأ من سطر (الكابشن:)",
          tk.extract_caption("[خطّاف] كلام\nمحتوى\nالكابشن: نسبة الإنجاز ليست تقديراً")
          == "نسبة الإنجاز ليست تقديراً")
    check("وإلا يُؤخذ الخطّاف بعد تنظيف الأقواس",
          tk.extract_caption("[خطّاف 3 ثوان] أكثر رقم نخدع فيه أنفسنا في المقاولات\nثم المحتوى")
          .startswith("أكثر رقم"))
    check("عمود caption يتقدّم على الاستخراج",
          tk.caption_for({"caption": "كابشن يدوي", "content": "الكابشن: آلي"}) == "كابشن يدوي")
    check("الملف الصغير يُرفع بجزء واحد", tk._chunks(9 * 1024 * 1024) == (9 * 1024 * 1024, 1))
    check("الملف الكبير يُجزّأ ضمن حدود تيك توك",
          tk._chunks(150 * 1024 * 1024)[0] <= tk.MAX_CHUNK and tk._chunks(150 * 1024 * 1024)[1] == 2)

    mock = TikTokMock()
    video = tmp / "reel.mp4"
    payload = b"\x00\x00\x00\x18ftypmp42" + b"TESTVIDEO" * 4096
    video.write_bytes(payload)
    cfg = {"tiktok": {"client_key": "ck", "client_secret": "cs", "redirect_uri": "http://x",
                      "access_token": "ACCESS", "refresh_token": "REFRESH",
                      "mode": "inbox", "api_base": mock.base}}
    try:
        row = {"content": "سكربت الفيديو\nالكابشن: نسبة الإنجاز ليست تقديراً",
               "media_path": str(video), "caption": ""}
        status, note = publish.post_tiktok(cfg, row)
        check("الرفع في وضع inbox ينتهي بحالة manual", status == "manual", f"{status} — {note[:60]}")
        check("كل بايتات الفيديو وصلت", mock.uploaded == payload,
              f"{len(mock.uploaded)}/{len(payload)} بايت")
        check("استُدعيت نقطة inbox لا النشر المباشر",
              any(p.endswith("/inbox/video/init/") for p in mock.paths()))
        check("رفع البايتات تم بترويسة Content-Range",
              any(c[0] == "PUT" and c[2] and c[2].startswith("bytes 0-") for c in mock.calls))
        check("رمز الوصول أُرسل في الترويسة",
              any(len(c) > 3 and c[3] == "Bearer ACCESS" for c in mock.calls))

        mock.calls.clear()
        cfg["tiktok"]["mode"] = "direct"
        cfg["tiktok"]["privacy_level"] = "SELF_ONLY"
        status, note = publish.post_tiktok(cfg, row)
        init = next((c for c in mock.calls if c[1].endswith("/video/init/")), None)
        check("النشر المباشر ينتهي بحالة posted", status == "posted", f"{status} — {note[:60]}")
        check("النشر المباشر يرسل post_info بالخصوصية والكابشن",
              bool(init) and init[2]["post_info"]["privacy_level"] == "SELF_ONLY"
              and "نسبة الإنجاز" in init[2]["post_info"]["title"])

        mock.calls.clear()
        cfg["tiktok"]["access_token"] = ""
        tk.refresh_access_token(cfg, persist=False)
        check("تجديد الرمز يعمل بـ refresh_token", cfg["tiktok"]["access_token"] == "NEW_ACCESS")
        check("معلومات الحساب تُقرأ", tk.creator_info(cfg).get("creator_username") == "yahya")
        check("حالة النشر تُتابَع",
              tk.fetch_status(cfg, "v_pub_7788").get("status") == "PUBLISH_COMPLETE")

        check("بلا فيديو: الصف يبقى يدوياً بلا رفع",
              publish.post_tiktok(cfg, {"content": "سكربت", "media_path": ""})[0] == "manual")
        check("مسار فيديو خاطئ يُبلَّغ كخطأ لا كنجاح",
              publish.post_tiktok(cfg, {"content": "س", "media_path": "/no/such.mp4"})[0] == "error")
        check("حساب غير مربوط يُتخطّى بوضوح",
              publish.post_tiktok({"tiktok": {}}, row)[0] == "skip")
    finally:
        mock.stop()


def test_voice(tmp: Path) -> None:
    section("10) صوت يحيى: العيّنات تُحقن، والفارغ يُتجاهل بهدوء")
    persona, facts = P.load_persona(), P.load_facts()

    # الملف كما يُسلَّم (عناوين وقوالب فارغة): لا يخترع صوتاً
    shipped = P.load_voice()
    check("الفراغات النموذجية لا تُقرأ كعيّنات", shipped["samples"] == [],
          f"{len(shipped['samples'])} عيّنة")
    check("تفضيلات الصياغة الافتراضية تُقرأ", bool(shipped["prefs"].get("sentence_length")))

    sample_file = tmp / "voice.md"
    sample_file.write_text("""# عيّنات

## ١. كيف تشرح مشكلة فنية
```
المستخلص تأخر لأن المقاس ما طابق المخطط. صوّرنا، وثّقنا، وأرسلنا للاستشاري نفس اليوم.
```

## ٢. كيف تختلف مع رأي سائد
```
(اكتب هنا)
```

## ٣. درس من تعثّر
```
خسرت شهراً كاملاً لأني وثقت بتقدير شفهي. اليوم ما أعتمد رقماً بلا مستند.
```

## تفضيلات الصياغة
```yaml
sentence_length: "قصيرة"
formality: "مهني قريب"
emoji: "لا"
avoid_words: ["نقلة نوعية", "ثورة"]
```
""", encoding="utf-8")

    original = P.VOICE_PATH
    try:
        P.VOICE_PATH = sample_file
        v = P.load_voice()
        check("العيّنات المكتوبة تُقرأ", len(v["samples"]) == 2, f"{len(v['samples'])}")
        check("القالب الفارغ بينها يُتخطّى",
              all("اكتب هنا" not in s["text"] for s in v["samples"]))
        check("عناوين الأقسام تُلتقط مع العيّنة",
              "مشكلة فنية" in v["samples"][0]["title"])
        check("التفضيلات تُقرأ كـ YAML لا كعيّنة", v["prefs"].get("sentence_length") == "قصيرة")

        prompt = P.build_system_prompt(persona, facts, "ar", v)
        check("العيّنة تدخل تعليمات النموذج", "المستخلص تأخر" in prompt)
        check("الكلمات الممنوعة تصل كقاعدة ملزمة", "نقلة نوعية" in prompt)
        check("التعليمات تمنع اقتباس وقائع العيّنات",
              "لا مرجع المعلومات" in prompt or "لا تقتبس وقائعها" in prompt)
        check("طول التعليمات يبقى معقولاً", len(prompt) < 9000, f"{len(prompt)} حرفاً")

        empty = tmp / "empty.md"
        empty.write_text("# لا شيء\n", encoding="utf-8")
        P.VOICE_PATH = empty
        bare = P.build_system_prompt(persona, facts, "ar", P.load_voice())
        check("بلا عيّنات: التعليمات تعمل بالقواعد العامة",
              "عيّنات بقلم يحيى" not in bare and "قواعد لا تُكسر" in bare)
    finally:
        P.VOICE_PATH = original


def test_saudi_first() -> None:
    section("9) السعودية أولاً: الأنشطة الستة، والمطابقة العربية، والمناسبات")
    import calendar_sa
    persona, now = P.load_persona(), datetime.now(timezone.utc)

    def score(title, summary="", stype="industry_publication", hours=5):
        return P.score_story(P.Story(title=title, summary=summary, source="t", source_type=stype,
                                     published=now - timedelta(hours=hours)), persona, now, {})

    # المطابقة العربية مع السوابق واللواحق — أكثر ما كان يُفقد الأخبار السعودية
    check("«بالرياض» تُطابق «الرياض»", P._hits(P.normalize("مشاريع بالرياض"), ["الرياض"]) != [])
    check("«للمقاولين» تُطابق «مقاول»", P._hits(P.normalize("للمقاولين مهلة"), ["مقاول"]) != [])
    check("«والمقاولات» تُطابق «مقاولات»", P._hits(P.normalize("والمقاولات تنمو"), ["مقاولات"]) != [])
    check("«رياضة» لا تُطابق «الرياض»", P._hits(P.normalize("بطولة رياضة"), ["الرياض"]) == [])

    gov = score("وزارة الموارد البشرية تُلزم منشآت المقاولات بتوثيق العقود عبر منصة قوى",
                "غرامات عند المخالفة.", "official_government", 4)
    site = score("أمانة جدة ترصد عيوب تنفيذ وتشققات في مبانٍ حديثة",
                 "مخالفات كود البناء وسلامة العمال.")
    tender = score("ترسية مشاريع بنية تحتية بالرياض على مقاولين محليين",
                   "مناقصات ومستخلصات وفق العقد الموحد.")
    global_ai = score("OpenAI launches enterprise AI agent platform", "Automation worldwide.",
                      "major_international_publication")
    global_ref = score("Contractors adopt BIM on infrastructure projects", "Productivity study.")
    noise = score("Global shoe brand announces new sneaker line", "Fashion.", "unknown_website", 2)

    check("قرار وزاري يُصنَّف قرارات حكومية", gov.meta["pillar"] == "government_decisions",
          gov.meta["pillar"])
    check("أخطاء البناء تُصنَّف عامل البناء وأخطاء البناء", site.meta["pillar"] == "site_quality")
    check("الترسيات تُصنَّف مقاولات ومشاريع", tender.meta["pillar"] == "construction_projects")
    check("الجهة الحكومية إشارة سعودية", gov.meta["region"] == "saudi_arabia")
    check("الخبر السعودي يتقدم على العالمي داخل النشاط نفسه",
          tender.scores["total"] > global_ref.scores["total"],
          f"{tender.scores['total']} مقابل {global_ref.scores['total']}")
    check("الذكاء الاصطناعي العالمي يبقى مطروحاً",
          global_ai.scores["total"] >= persona["thresholds"]["pipeline_entry"],
          f"{global_ai.scores['total']}")
    check("وُسم بأنه يحتاج ربطاً سعودياً", "سعودي" in global_ai.meta["saudi_note"])
    check("الضجيج العالمي يسقط", noise.scores["total"] < 20, f"{noise.scores['total']}")
    check("الأنشطة الستة تُرصد في البيانات الوصفية", bool(gov.meta["activities"]))

    # رادار الترند: إشارة لا خبر
    trend = P.Story(title="ترند: جدل حول مهلة التوطين في المقاولات", source="trends",
                    source_type="social_media", published=now, meta={"kind": "trend"})
    radar = NE.trend_radar([trend], persona)
    check("الترند المتقاطع مع أنشطتك يُرصد", radar and radar[0]["relevant"],
          str(radar[0]["matched"]) if radar else "لا شيء")
    off = NE.trend_radar([P.Story(title="ترند: مباراة كرة قدم", source="t",
                                  source_type="social_media", published=now,
                                  meta={"kind": "trend"})], persona)
    check("الترند خارج أنشطتك يُستبعد من الاقتراح", off and not off[0]["relevant"])

    # الرزنامة السعودية
    cal = calendar_sa.load_calendar()
    names = [o["name"] for o in cal["occasions"]]
    check("الرزنامة تحوي اليوم الوطني ويوم التأسيس",
          "اليوم الوطني السعودي" in names and "يوم التأسيس" in names)
    nat = calendar_sa.upcoming(400, date(2026, 9, 1), cal)
    hit = next((o for o in nat if o["key"] == "national_day"), None)
    check("اليوم الوطني يُحسب في 23 سبتمبر", bool(hit) and hit["date"] == date(2026, 9, 23))
    check("لا ينبّه قبل الأوان (22 يوماً والمهلة 14)", bool(hit) and not hit["due"],
          f"بعد {hit['days_away']} يوماً، المهلة {hit['lead_days']}" if hit else "")
    inside = next((o for o in calendar_sa.upcoming(400, date(2026, 9, 15), cal)
                   if o["key"] == "national_day"), None)
    check("وينبّه حين تدخل المهلة (قبل 8 أيام)", bool(inside) and inside["due"],
          f"بعد {inside['days_away']} يوماً" if inside else "")
    check("due_now يعيد المستحق فقط",
          all(o["due"] for o in calendar_sa.due_now(date(2026, 9, 15), cal)))
    ramadan = next((o for o in calendar_sa.upcoming(400, date(2027, 1, 1), cal)
                    if o["key"] == "ramadan"), None)
    check("المناسبات الهجرية تُحسب بتقويم أم القرى",
          bool(ramadan) and ramadan["date"].year == 2027 and ramadan["date"].month == 2,
          str(ramadan["date"]) if ramadan else "تعذّر — ثبّت hijridate")
    check("لكل مناسبة زاوية مرتبطة بتخصصه",
          all(o.get("angle") for o in cal["occasions"]))


def test_data_stories(tmp: Path) -> None:
    section("13) قصص البيانات: الحواجز تُفرض برمجياً لا ثقةً")
    import data_stories as DS

    def metric(**kw):
        base = {"key": "k", "label": "نسبة إعادة التنفيذ", "value": 9, "unit": "%",
                "basis": "من 12 مشروعاً", "period": "2026", "sensitivity": "safe",
                "angle": "كلفة إعادة العمل تُدفع مرتين"}
        base.update(kw)
        return base

    check("رقم مكتمل وآمن يمرّ", DS.validate(metric())[0])
    check("بلا قيمة يُرفض", not DS.validate(metric(value=None))[0])
    check("بلا أساس يُرفض", not DS.validate(metric(basis=None))[0])
    check("أساس بلا عدد يُرفض", not DS.validate(metric(basis="من عدة مشاريع"))[0])
    check("أساس دون حد التجميع يُرفض",
          not DS.validate(metric(basis="من 3 مشاريع"))[0],
          str(DS.validate(metric(basis="من 3 مشاريع"))[1]))
    check("internal لا يخرج في منشور", not DS.validate(metric(sensitivity="internal"))[0])
    check("never محجوب تماماً", not DS.validate(metric(sensitivity="never"))[0])
    check("تصنيف مجهول يُرفض", not DS.validate(metric(sensitivity=""))[0])

    for money in ("متوسط قيمة المستخلص 400 ألف ريال", "التوفير بلغ 2 مليون"):
        ok, why = DS.validate(metric(label=money))
        check(f"مبلغ مالي مطلق يُحجب: {money[:28]}", not ok and any("مالي" in w for w in why))
    ok, _ = DS.validate(metric(angle="وفّرنا ما يعادل 500 ألف دولار"))
    check("المبلغ في الزاوية يُحجب أيضاً", not ok)

    mixed = [metric(key="a"), metric(key="b", sensitivity="internal"),
             metric(key="c", value=None), metric(key="d", basis="من 2 مشروع")]
    check("publishable يمرّر الآمن فقط",
          [m["key"] for m in DS.publishable(mixed)] == ["a"])

    check("الصياغة تذكر الأساس دائماً", "من 12 مشروعاً" in DS.describe(metric()))
    check("النسبة تُصاغ بعلامتها", DS.describe(metric()).count("%") == 1)

    shipped = DS.load_metrics()
    check("الملف المُسلَّم لا يحوي أرقاماً مخترعة",
          all(m.get("value") is None for m in shipped), "قيم جاهزة بلا إذن يحيى")
    check("كل بند في الملف له زاوية وتصنيف",
          all(m.get("angle") and m.get("sensitivity") for m in shipped))

    # قصة البيانات لا تكون خضراء مهما بدا النص آمناً
    import generate_posts as G
    persona = P.load_persona()
    row = G.build_row(1, datetime.now(), "linkedin_post",
                      "شرح مبسط لمؤشر إعادة التنفيذ في المشاريع", persona,
                      pillar="construction_projects", content_type="data_story",
                      language="ar", previous=[])
    check("قصة البيانات تُلزَم بالمراجعة البشرية", row["approval_level"] == "yellow",
          row["approval_level"])
    check("سبب الإلزام مكتوب للمراجع", "قصة بيانات" in row["review_notes"])
    plain = G.build_row(2, datetime.now(), "linkedin_post",
                        "شرح مبسط لمؤشر إعادة التنفيذ في المشاريع", persona,
                        pillar="construction_projects", content_type="educational",
                        language="ar", previous=[])
    check("المحتوى التعليمي نفسه يبقى أخضر", plain["approval_level"] == "green")

    prompt = G.data_story_prompt(persona, P.load_facts(), metric(), "linkedin_post", "ar")
    check("التعليمات تمنع أي رقم آخر", "أي رقم غير الرقم أعلاه" in prompt)
    check("التعليمات تمنع أسماء العملاء والمبالغ", "اسم أي عميل أو مشروع" in prompt)
    check("التعليمات توجب ذكر الأساس", "أساسه صراحةً" in prompt)


def test_learned_times(tmp: Path) -> None:
    section("12) مواعيد النشر تتعلّم — داخل نوافذ الاستراتيجية فقط")
    import feedback as F
    import generate_posts as G
    persona = P.load_persona()

    def rows(entries):
        """entries = [(platform, time, engagement_scale, count)]"""
        out, i = [], 0
        for platform, when, scale, count in entries:
            for _ in range(count):
                i += 1
                likes = 5000 * scale * 0.5
                out.append({"id": i, "date": "2026-10-05", "time": when, "platform": platform,
                            "pillar": "construction_projects", "language": "ar",
                            "impressions": 5000, "likes": round(likes),
                            "comments": round(likes * .1), "shares": round(likes * .08),
                            "saves": round(likes * .05), "profile_visits": round(likes * .3),
                            "followers_gained": round(likes * .05), "clicks": 5, "hook": "h"})
        return out

    # لينكدإن: 09:00 يتفوق على 08:30 — كلاهما داخل النافذة 07:30-10:00
    learned = F.learn_post_times(rows([("linkedin_post", "08:30", 0.02, 4),
                                       ("linkedin_post", "09:00", 0.09, 4)]), persona)
    check("يعتمد الوقت الأعلى تفاعلاً داخل النافذة",
          learned.get("linkedin_post", {}).get("time") == "09:00", str(learned))

    # وقت شاذ خارج النافذة مهما علا تفاعله
    wild = F.learn_post_times(rows([("linkedin_post", "03:00", 0.5, 6),
                                    ("linkedin_post", "08:30", 0.03, 4)]), persona)
    check("يرفض الوقت خارج نافذة الاستراتيجية مهما علا تفاعله",
          wild.get("linkedin_post", {}).get("time") == "08:30", str(wild))

    # عيّنة قليلة لا تُعتمد
    thin = F.learn_post_times(rows([("linkedin_post", "09:30", 0.9, 2)]), persona)
    check("عيّنة دون الحد الأدنى لا تُعتمد", "linkedin_post" not in thin, str(thin))
    check("بلا بيانات: لا مواعيد متعلَّمة", F.learn_post_times([], persona) == {})

    # كل منصة تتعلّم وقتها
    multi = F.learn_post_times(rows([("linkedin_post", "09:00", 0.08, 4),
                                     ("twitter", "21:00", 0.07, 4),
                                     ("twitter", "08:00", 0.02, 3)]), persona)
    check("التعلّم مستقل لكل منصة",
          multi.get("twitter", {}).get("time") == "21:00"
          and multi.get("linkedin_post", {}).get("time") == "09:00", str(multi))

    # التطبيق في المولّد
    t, src = G.post_time("linkedin_post", persona, multi)
    check("المولّد يستخدم الموعد المتعلَّم", t == "09:00" and src.startswith("متعلَّم"), f"{t} {src}")
    t2, src2 = G.post_time("linkedin_post", persona, {})
    check("وبلا تعلّم يستخدم افتراضي persona.yml", t2 == "08:30" and src2 == "افتراضي", f"{t2} {src2}")
    t3, src3 = G.post_time("منصة_غير_معروفة", persona, {})
    check("منصة غير معرَّفة تأخذ موعداً احتياطياً", bool(t3), f"{t3} {src3}")

    check("كل منصة في الإيقاع الأسبوعي لها نافذة وافتراضي",
          all(p in (persona["posting"]["defaults"]) and p in persona["posting"]["windows"]
              for p in ("twitter", "twitter_thread", "linkedin_post", "article",
                        "instagram_carousel", "tiktok_script")))

    # التقرير يشرح، ويحفظ المواعيد حيث يقرؤها المولّد
    perf_file, weights_file, report_file = tmp / "p.csv", tmp / "w.yml", tmp / "r.md"
    with perf_file.open("w", newline="", encoding="utf-8") as fh:
        data = rows([("linkedin_post", "09:00", 0.08, 4), ("twitter", "21:00", 0.06, 4)])
        w = csv.DictWriter(fh, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    old = (F.PERF, F.WEIGHTS, F.REPORT, F.QUEUE)
    try:
        F.PERF, F.WEIGHTS, F.REPORT, F.QUEUE = perf_file, weights_file, report_file, tmp / "none.csv"
        F.learn(None)
        saved = yaml.safe_load(weights_file.read_text(encoding="utf-8"))
        check("المواعيد تُحفظ في ملف الأوزان",
              saved.get("best_post_times", {}).get("linkedin_post", {}).get("time") == "09:00")
        text = report_file.read_text(encoding="utf-8")
        check("التقرير يعرض المواعيد المعتمدة", "مواعيد النشر المعتمدة آلياً" in text)
        check("التقرير يعرض أفضل أيام الأسبوع إرشادياً", "أفضل أيام الأسبوع" in text)
    finally:
        F.PERF, F.WEIGHTS, F.REPORT, F.QUEUE = old


def test_gov_watch(tmp: Path) -> None:
    section("11) مرصد القرارات الحكومية: استخراج من صفحات بلا RSS")
    import gov_watch as GW
    persona, now = P.load_persona(), datetime.now(timezone.utc)
    fx = Path(__file__).resolve().parent / "fixtures" / "gov"

    pages = tmp / "gov_pages"
    pages.mkdir(exist_ok=True)
    for f in fx.glob("*.html"):
        shutil.copy(f, pages / f.name)
    server = FeedServer(pages)

    try:
        hrsd = {"name": "وزارة الموارد البشرية", "url": f"{server.base}/hrsd_news.html",
                "topic": "نظام العمل", "priority": 1, "selectors": {},
                "keywords": ["نطاقات", "التوطين", "نظام العمل", "قوى", "العمالة", "قرار"]}
        sca = {"name": "الهيئة السعودية للمقاولين", "url": f"{server.base}/sca_news.html",
               "topic": "تصنيف المقاولين", "priority": 1, "selectors": {},
               "keywords": ["المقاولين", "التصنيف", "العقد الموحد", "المقاول"]}

        rows, how = GW.entity_items("hrsd", hrsd)          # جلب HTTP فعلي
        titles = [r["title"] for r in rows]
        check("جلب صفحة حكومية واستخراج قائمة الأخبار", len(rows) == 5, f"{len(rows)} عنصراً")
        check("الروابط مطلقة لا نسبية", all(r["url"].startswith("http") for r in rows))
        check("روابط التنقل والتذييل استُبعدت",
              not any(t in titles for t in ("الرئيسية", "اتصل بنا", "الخصوصية")))
        check("الاستخراج التلقائي يحدد بنية القائمة", how.startswith("auto:"), how[:40])

        rows2, _ = GW.entity_items("sca", sca)
        check("يعمل مع بنية صفحة مختلفة تماماً", len(rows2) == 4, f"{len(rows2)}")
        check("يختار قائمة الأخبار لا قائمة التنقل المشابهة",
              all("عن الهيئة" not in r["title"] for r in rows2))

        # المحددات الصريحة تتقدم على التخمين
        hrsd_sel = dict(hrsd, selectors={"item": "div.news-card", "title": "h3",
                                         "link": "a", "date": "span.news-card__date"})
        rows3, how3 = GW.entity_items("hrsd", hrsd_sel)
        check("المحددات الصريحة تُستخدم حين تُضبط", how3 == "selectors")
        check("المحددات تلتقط التاريخ أيضاً", rows3 and rows3[0]["date_text"] == "2026-10-28",
              rows3[0]["date_text"] if rows3 else "—")

        stories = GW.to_stories("hrsd", hrsd, rows)
        for s in stories:
            P.score_story(s, persona, now, {})
        top = max(stories, key=lambda s: s.scores["total"])
        check("الخبر الحكومي يُصنَّف مصدراً رسمياً",
              all(s.source_type == "official_government" for s in stories))
        check("قرار تشغيلي يتصدر لا خبر احتفالي",
              any(w in top.title for w in ("قوى", "نطاقات", "أجير", "لائحة")), top.title[:60])
        check("أخبار الجهة الواحدة تتفاوت بدل أن تتساوى",
              len({round(s.scores["total"]) for s in stories}) > 1,
              str(sorted({round(s.scores["total"]) for s in stories})))
        check("يتجاوز عتبة خط الإنتاج بفارق مريح",
              top.scores["total"] >= persona["thresholds"]["deep_dive"],
              f"{top.scores['total']}")
        check("العمود هو القرارات الحكومية", top.meta["pillar"] == "government_decisions",
              top.meta["pillar"])
        ceremony = next(s for s in stories if "تكرّم" in s.title)
        check("الخبر الاحتفالي يسقط دون عتبة خط الإنتاج",
              ceremony.scores["total"] < persona["thresholds"]["pipeline_entry"],
              f"{ceremony.scores['total']}")
        check("خبر الجهة سعودي ولو خلا العنوان من ذكر السعودية",
              ceremony.meta["region"] == "saudi_arabia")

        broken = dict(hrsd, url=f"{server.base}/does_not_exist.html")
        try:
            GW.entity_items("x", broken)
            ok = False
        except Exception:        # noqa: BLE001 — المطلوب أن يرتفع الخطأ ليُلتقط في cmd_fetch
            ok = True
        check("الصفحة المفقودة تُبلَّغ كخطأ لا كصمت", ok)
    finally:
        server.stop()


def test_repo_integrity() -> None:
    section("7) سلامة المستودع والإعدادات")
    persona = P.load_persona()
    check("مجموع أوزان الملاءمة = 100", sum(persona["relevance_weights"].values()) == 100)
    check("مجموع حصص الأعمدة = 100%",
          abs(sum(p["share"] for p in persona["content_pillars"].values()) - 1.0) < 1e-9)
    check("كل عمود له تسمية عربية", all(p.get("label_ar") for p in persona["content_pillars"].values()))
    check("ملف الحقائق صالح ويحمل الهوية", bool(P.load_facts()["identity"]["name_en"]))
    check("مصادر الإنتاج مصنّفة بمصداقية معروفة",
          all(f.get("type") in persona["source_credibility"]
              for f in yaml.safe_load((AUTOMATION / "sources.yml").read_text(encoding="utf-8"))["feeds"]))
    check("الأسرار مستبعدة من git",
          "automation/config.yml" in (ROOT / ".gitignore").read_text(encoding="utf-8"))
    check("لا مفاتيح مكتوبة في المستودع",
          not re.search(r"sk-ant-[A-Za-z0-9]{20,}", "".join(
              p.read_text(encoding="utf-8", errors="ignore")
              for p in AUTOMATION.rglob("*.py"))))
    for script in ("persona.py", "news_engine.py", "generate_posts.py", "publish.py",
                   "feedback.py", "tiktok.py", "tiktok_auth.py", "gov_watch.py",
                   "calendar_sa.py", "data_stories.py"):
        check(f"{script} يُحلَّل بلا أخطاء نحوية",
              compile((AUTOMATION / script).read_text(encoding="utf-8"), script, "exec") is not None)


def main() -> int:
    global VERBOSE
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    VERBOSE = ap.parse_args().verbose

    print("\033[1m" + "═" * 78)
    print("  اختبار النظام الكامل — محرك الاستخبارات والمحتوى")
    print("═" * 78 + "\033[0m")

    tmp = Path(tempfile.mkdtemp(prefix="brand-engine-test-"))
    render_fixtures(tmp / "feeds")
    server = FeedServer(tmp / "feeds")
    print(f"خادم التغذيات المحلي: {server.base}   |   مجلد العمل: {tmp}")

    try:
        test_persona_logic()
        test_discovery(tmp, server)
        queue = test_generation(tmp)
        test_publish_gate(tmp, queue)
        test_learning(tmp, queue)
        test_weekly_report(tmp)
        test_tiktok(tmp)
        test_saudi_first()
        test_voice(tmp)
        test_gov_watch(tmp)
        test_learned_times(tmp)
        test_data_stories(tmp)
        test_repo_integrity()
    finally:
        server.stop()
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = [label for label, ok, _ in RESULTS if not ok]
    print("\n" + "═" * 78)
    if failed:
        print(f"\033[31m  {passed}/{len(RESULTS)} نجح — أخفق {len(failed)}:\033[0m")
        for label in failed:
            print(f"    ✗ {label}")
    else:
        print(f"\033[32m  كل الاختبارات نجحت: {passed}/{len(RESULTS)}\033[0m")
    print("═" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
