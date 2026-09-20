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
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import types
from datetime import datetime, timedelta, timezone
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
    for pillar, rate, n in (("construction_engineering", 0.09, 5), ("ai_technology", 0.04, 5),
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
    check("وزن العمود الناجح ارتفع", weights["construction_engineering"] > 1.0,
          f"{weights['construction_engineering']}×")
    check("وزن العمود الضعيف انخفض", weights["real_estate"] < 1.0, f"{weights['real_estate']}×")
    check("العمود بلا بيانات يبقى محايداً", weights["investment"] == 1.0)
    check("المضاعِف محصور ضمن الحدود",
          all(F.BOUNDS[0] <= v <= F.BOUNDS[1] for v in weights.values()))
    check("تقرير التعلّم يشرح سبب كل وزن", "أداء" in F.REPORT.read_text(encoding="utf-8"))

    # الأثر الفعلي: الوزن الجديد يغيّر ترتيب الأخبار
    persona, now = P.load_persona(), datetime.now(timezone.utc)
    story = P.Story(title="Contractors adopt BIM and digital twin on infrastructure projects",
                    summary="Construction productivity study.", source_type="industry_publication",
                    published=now)
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
                    "التقنية", "الإنشاءات والهندسة", "الفرصة السعودية", "الموضوع المقترح للتعمّق"):
        check(f"بند التقرير: {heading}", heading in text)


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
    for script in ("persona.py", "news_engine.py", "generate_posts.py", "publish.py", "feedback.py"):
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
