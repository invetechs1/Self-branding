#!/usr/bin/env python3
"""طبقة الشخصية والذكاء — القلب المشترك بين محرك الأخبار ومولّد المحتوى.

تقرأ profile/persona.yml (الأوزان والعتبات والكلمات المفتاحية) و profile/facts.yml
(الوقائع الشخصية المسموح استخدامها) و automation/learning/weights.yml (ما تعلّمه النظام).

تنفّذ من المواصفة:
  §19 مصداقية المصادر · §20 معادلة الملاءمة · §21 تجميع المكرر · §22 التحقق من الحقائق
  §24 طبقة الرؤية · §26 مزيج الأعمدة · §37 مستويات الاعتماد · §44 خريطة قيادة الفكر
  §45 اكتشاف الفرص · §46 اكتشاف الاتجاهات

كل الدوال نقية (بلا شبكة) — لذا يمكن اختبارها: python automation/persona.py --self-test
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PERSONA_PATH = ROOT / "profile" / "persona.yml"
VOICE_PATH = ROOT / "profile" / "voice-samples.md"
FACTS_PATH = ROOT / "profile" / "facts.yml"
WEIGHTS_PATH = ROOT / "automation" / "learning" / "weights.yml"

# ── ربط المصطلحات بأعمدة المحتوى (§25) ──
PILLAR_TERMS = {
    "construction_projects": [
        "مقاولات", "مقاول", "مشروع إنشائي", "ترسية", "مناقصة", "منافسة", "مستخلص", "أمر تغييري",
        "مقاول الباطن", "البنية التحتية", "خرسانة", "سفلتة", "تشطيبات", "إدارة المشاريع",
        "هيئة المقاولين", "المشاريع الحكومية", "تأخر المشروع", "غرامة تأخير", "جدولة",
        "contractor", "construction", "tender", "infrastructure", "project management", "contech"],
    "ai_technology": [
        "ذكاء اصطناعي", "نموذج لغوي", "وكيل ذكي", "أتمتة", "تعلم آلي", "سدايا", "رؤية حاسوبية",
        "تحول رقمي", "برمجيات", "منصة رقمية", "مركز بيانات", "روبوت", "نظام ذكي",
        "artificial intelligence", "ai agent", "llm", "automation", "machine learning", "erp",
        "saas", "copilot", "computer vision", "data center", "digital twin", "bim"],
    "government_decisions": [
        "وزارة الموارد البشرية", "التأمينات الاجتماعية", "وزارة التجارة", "الزكاة والضريبة",
        "الفاتورة الإلكترونية", "نطاقات", "السعودة", "التوطين", "مكتب العمل", "قوى", "مساند",
        "نظام العمل", "لائحة", "قرار وزاري", "تعميم", "مجلس الوزراء", "وزارة البلديات",
        "المحتوى المحلي", "اعتماد", "نظام المنافسات", "إلزام", "اشتراط", "اعتباراً من",
        "regulation", "ministerial", "mandate", "compliance"],
    "site_quality": [
        "عامل بناء", "العمالة", "سلامة الموقع", "إصابات العمل", "السلامة المهنية", "أخطاء التنفيذ",
        "عيوب البناء", "تشققات", "العزل", "كود البناء", "جودة التنفيذ", "الإشراف الهندسي",
        "مخالفات البناء", "رخصة بناء", "الأمانة", "بلدي", "سقالات", "شهادة إشغال", "انهيار",
        "building defect", "site safety", "worker safety", "building code", "inspection"],
    "saudi_economy": [
        "الاقتصاد السعودي", "رؤية 2030", "صندوق الاستثمارات", "الرياض", "نيوم", "المشاريع الكبرى",
        "الناتج المحلي", "القطاع الخاص", "الاستثمار الأجنبي", "تداول", "طرح عام", "نمو",
        "saudi economy", "vision 2030", "pif", "giga-project", "gdp", "non-oil"],
    "saudi_trends": [
        "ترند", "الأكثر تداولاً", "يتصدر", "وسم", "هاشتاق", "الأكثر بحثاً", "جدل", "تفاعل",
        "حديث السوشيال", "trending", "viral"],
    "real_estate": [
        "عقار", "تطوير عقاري", "إسكان", "سكني", "تمويل عقاري", "أسعار الأراضي", "صندوق عقاري",
        "الطلب على المساكن", "سكني", "ريت", "real estate", "proptech", "housing", "mortgage", "reit"],
    "occasions": [
        "اليوم الوطني", "يوم التأسيس", "يوم العلم", "إجازة رسمية", "عيد الفطر", "عيد الأضحى",
        "رمضان", "موسم الرياض", "اليوم العالمي", "الاحتفال", "national day", "founding day"],
    "business_leadership": [
        "إدارة", "قيادة", "التوظيف", "الإنتاجية", "ثقافة العمل", "ريادة أعمال", "شركة ناشئة",
        "تمويل", "استثمار", "استحواذ", "leadership", "management", "startup", "funding", "hiring"],
}

_AR_NORMALIZE = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": ""})


def rel(path: Path) -> str:
    """مسار للعرض نسبةً لجذر المستودع — وبالمسار الكامل إن كان خارجه (اختبار/مجلد مخصص)."""
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize(text: str) -> str:
    """تطبيع نص عربي/إنجليزي للمطابقة: حروف صغيرة، بلا تشكيل، ألف/ياء/تاء موحّدة."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.translate(_AR_NORMALIZE))


# سوابق ولواحق عربية شائعة — بدونها لا تُطابق «بالرياض» كلمةَ «الرياض»
_AR_PREFIX = r"(?:[وفبكل]{0,2}(?:ال)?)"
_AR_SUFFIX = r"(?:ات|ين|ون|ها|هم|هن|كم|يه|يت)?"
_AR_RANGE = "؀-ۿ"


def _is_arabic_term(t: str) -> bool:
    return any("؀" <= c <= "ۿ" for c in t)


def _ar_pattern(t: str) -> str:
    """نمط يتسامح مع السوابق واللواحق: «المقاولات» تُطابق «بالمقاولات» و«للمقاولين»."""
    core = t[2:] if t.startswith("ال") and len(t) > 4 else t
    return rf"(?<![{_AR_RANGE}\w]){_AR_PREFIX}{re.escape(core)}{_AR_SUFFIX}(?![{_AR_RANGE}])"


def _hits(text: str, terms) -> list:
    """المصطلحات الموجودة في النص.

    العربية تُطابَق بتسامح مع أدوات التعريف وحروف الجر الملتصقة (وهي أكثر ما يُفقِد المطابقة)،
    والإنجليزية بمطابقة كلمة كاملة للقصيرة واحتواء للمركّبة.
    """
    found = []
    for term in terms:
        t = normalize(str(term))
        if not t:
            continue
        if _is_arabic_term(t):
            if " " in t:
                if t in text:
                    found.append(term)
            elif re.search(_ar_pattern(t), text):
                found.append(term)
        elif " " in t or len(t) > 6:
            if t in text:
                found.append(term)
        elif re.search(rf"(?<![\w؀-ۿ]){re.escape(t)}(?![\w؀-ۿ])", text):
            found.append(term)
    return found


def _saturate(n: int, full: int = 3) -> float:
    """تحويل عدد المطابقات إلى 0..1 بتشبّع — 3 مطابقات ≈ الدرجة الكاملة."""
    return min(1.0, n / full) if full else 0.0


# ────────────────────────── التحميل ──────────────────────────

def load_persona() -> dict:
    return yaml.safe_load(PERSONA_PATH.read_text(encoding="utf-8"))


def load_facts() -> dict:
    return yaml.safe_load(FACTS_PATH.read_text(encoding="utf-8"))


PLACEHOLDER = re.compile(r"^\(?\s*(اكتب هنا|write here|\.\.\.)\s*\)?$", re.I)
CODE_BLOCK = re.compile(r"```(?:yaml)?\s*\n(.*?)```", re.S)
SECTION = re.compile(r"^##\s+(?:[٠-٩\d]+[.．]\s*)?(.+?)\s*$", re.M)


def load_voice() -> dict:
    """عيّنات صوت يحيى وتفضيلات صياغته — تُحقن كأمثلة يقلّدها النموذج.

    يتجاهل الأقسام الفارغة بهدوء: الملف الفارغ يعني «اكتب بالقواعد العامة»،
    ولا يُختلق صوت نيابةً عنه أبداً.
    """
    if not VOICE_PATH.exists():
        return {"samples": [], "prefs": {}}

    text = VOICE_PATH.read_text(encoding="utf-8")
    titles = SECTION.findall(text)
    blocks = CODE_BLOCK.findall(text)

    prefs, samples = {}, []
    for i, raw in enumerate(blocks):
        body = raw.strip()
        if not body or PLACEHOLDER.match(body):
            continue
        if body.lstrip().startswith(("sentence_length:", "formality:", "dialect_touch:")):
            try:
                prefs = yaml.safe_load(body) or {}
            except yaml.YAMLError:
                prefs = {}
            continue
        samples.append({"title": titles[i] if i < len(titles) else "عيّنة", "text": body})
    return {"samples": samples, "prefs": prefs}


def load_learning() -> dict:
    """أوزان التعلّم (§40): {pillar: multiplier} — 1.0 محايد."""
    if WEIGHTS_PATH.exists():
        data = yaml.safe_load(WEIGHTS_PATH.read_text(encoding="utf-8")) or {}
        return data.get("pillar_multipliers", {}) or {}
    return {}


# ────────────────────────── القصة ──────────────────────────

@dataclass
class Story:
    title: str
    summary: str = ""
    url: str = ""
    source: str = ""
    source_type: str = "unknown_website"   # مفتاح من persona.source_credibility
    published: datetime | None = None
    lang: str = "en"
    scores: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return normalize(f"{self.title} {self.summary}")

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        d["published"] = self.published.isoformat() if self.published else ""
        return d

    @staticmethod
    def from_dict(d: dict) -> "Story":
        d = dict(d)
        p = d.get("published")
        d["published"] = datetime.fromisoformat(p) if p else None
        return Story(**d)


# ────────────────────── مكوّنات الملاءمة (§20) ──────────────────────

def _interest_hits(text: str, terms, persona: dict) -> list:
    """اهتمام مطابق إذا ورد اسمه أو أي مرادف له (AI ≡ Artificial Intelligence)."""
    aliases = persona.get("interest_aliases", {})
    return [term for term in terms if _hits(text, [term] + list(aliases.get(term, [])))]


def activity_hits(story: Story, persona: dict) -> list:
    """أي من الأنشطة الستة تقع القصة داخله (الأساس السعودي للاكتشاف)."""
    out = []
    for key, spec in (persona.get("saudi_activities") or {}).items():
        hits = _hits(story.text, spec.get("keywords", []))
        if hits:
            out.append({"key": key, "label": spec.get("label_ar", key),
                        "pillar": spec.get("pillar", "saudi_economy"),
                        "weight": float(spec.get("weight", 1.0)), "hits": len(hits)})
    return sorted(out, key=lambda a: (-a["hits"] * a["weight"]))


def personal_interest_score(story: Story, persona: dict) -> tuple[float, list]:
    """اهتمام يحيى = خريطة الاهتمامات + أنشطته السعودية الستة (أيّهما أقوى)."""
    graph, tw = persona["interest_graph"], persona["interest_graph"]["tier_weights"]
    total, matched = 0.0, []
    for tier, weight in (("tier_1", tw["tier_1"]), ("tier_2", tw["tier_2"]), ("tier_3", tw["tier_3"])):
        hits = _interest_hits(story.text, graph[tier], persona)
        matched += hits
        total += weight * _saturate(len(hits), 3)

    # النشاط المعلن اهتمامٌ صريح: خبر داخل أحد الأنشطة الستة لا يُحسب صفراً لمجرد أنه عربي
    acts = activity_hits(story, persona)
    if acts:
        best = max(a["weight"] * _saturate(a["hits"], 2) for a in acts)
        total = max(total, min(1.0, best + 0.15 * (len(acts) - 1)))
        matched += [a["label"] for a in acts]
    return min(1.0, total), matched


def business_relevance_score(story: Story, persona: dict) -> tuple[float, list]:
    matched, best = [], 0.0
    for domain, spec in persona["business_domains"].items():
        hits = _hits(story.text, spec.get("keywords", []))
        if hits:
            matched.append(domain)
            best = max(best, _saturate(len(hits), 2))
    # التقاطع بين أكثر من مجال يعني ملاءمة أعلى لأعمال يحيى المتشابكة
    return min(1.0, best + 0.15 * max(0, len(matched) - 1)), matched


def saudi_gcc_score(story: Story, persona: dict) -> tuple[float, str]:
    geo, best_region, best = persona["geography"], "global", 0.0
    for region, terms in geo["terms"].items():
        if _hits(story.text, terms):
            w = geo["priority"].get(region, 0.4)
            if w > best:
                best, best_region = w, region
    # الجهات الحكومية السعودية إشارة سعودية كاملة.
    # (قائمة المتابعة saudi_watchlist مواضيع لا أماكن — "infrastructure" و"tourism" ليست دليلاً
    #  على أن الخبر سعودي، فاستخدامها هنا كان يجعل أي خبر عالمي يبدو سعودياً.)
    if _hits(story.text, persona.get("government_watchlist", [])):
        best = max(best, geo["priority"]["saudi_arabia"])
        best_region = "saudi_arabia"
    return best or geo["priority"]["global"], best_region


def strategic_score(story: Story, persona: dict) -> float:
    sig = persona["strategic_signals"]
    high, medium = len(_hits(story.text, sig["high"])), len(_hits(story.text, sig["medium"]))
    return min(1.0, 0.6 * _saturate(high, 2) + 0.4 * _saturate(medium, 2) + (0.4 if high else 0.0))


def audience_value_score(story: Story, persona: dict) -> float:
    return _saturate(len(_hits(story.text, persona["audience_value_signals"])), 2)


def freshness_score(story: Story, persona: dict, now: datetime) -> float:
    if not story.published:
        return 0.5
    th = persona["thresholds"]
    age_h = max(0.0, (now - story.published).total_seconds() / 3600)
    if age_h > th["freshness_max_age_hours"]:
        return 0.0
    return 0.5 ** (age_h / th["freshness_half_life_hours"])


def credibility_score(story: Story, persona: dict) -> float:
    return persona["source_credibility"].get(story.source_type, 20) / 100


def is_arabic(text: str) -> bool:
    """هل النص عربي في جوهره؟ (يُستخدم لتفضيل المصادر العربية)"""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    arabic = sum(1 for c in letters if "\u0600" <= c <= "\u06ff")
    return arabic / len(letters) > 0.4


def pillars_ranked(story: Story) -> list:
    """أعمدة المحتوى مرتّبة حسب قوة تطابقها مع القصة (§25)."""
    ranked = sorted(((len(_hits(story.text, terms)), p) for p, terms in PILLAR_TERMS.items()),
                    reverse=True)
    return [p for n, p in ranked if n] or ["ai_technology"]


def pillar_of(story: Story, persona: dict) -> str:
    """أقوى عمود محتوى يناسب القصة. القصة متعددة الأعمدة يحسمها مزيج المحتوى لاحقاً."""
    return pillars_ranked(story)[0]


def leadership_boost(story: Story, persona: dict) -> tuple[float, str]:
    """§44: تقاطعات قيادة الفكر تُعطى دفعة — أعلاها AI × Construction × Business."""
    graph = persona["thought_leadership_graph"]
    candidates = [graph["primary"]] + list(graph["secondary"])
    for c in candidates:
        if all(_hits(story.text, [term]) or _hits(story.text, PILLAR_TERMS.get(_pillar_alias(term), []))
               for term in c["intersection"]):
            return c["boost"], " × ".join(c["intersection"])
    return 1.0, ""


def _pillar_alias(term: str) -> str:
    return {"AI": "ai_technology", "Construction": "construction_projects", "Business": "business_leadership",
            "Real Estate": "real_estate", "Technology": "ai_technology", "Project Management": "construction_projects",
            "Saudi Arabia": "saudi_economy", "Entrepreneurship": "business_leadership", "ERP": "ai_technology",
            "AI Agents": "ai_technology", "Business Automation": "ai_technology",
            "Traditional Industries": "construction_projects"}.get(term, "")


def score_story(story: Story, persona: dict, now: datetime | None = None,
                learning: dict | None = None) -> Story:
    """يحسب درجة الملاءمة 0-100 ويخزّنها في story.scores (§20)."""
    now = now or datetime.now(timezone.utc)
    learning = learning if learning is not None else load_learning()
    w = persona["relevance_weights"]

    interest, interest_hits = personal_interest_score(story, persona)
    business, domains = business_relevance_score(story, persona)
    geo, region = saudi_gcc_score(story, persona)
    strategic = strategic_score(story, persona)
    audience = audience_value_score(story, persona)
    fresh = freshness_score(story, persona, now)
    cred = credibility_score(story, persona)

    base = (w["personal_interest"] * interest + w["business_relevance"] * business
            + w["saudi_gcc_relevance"] * geo + w["strategic_importance"] * strategic
            + w["audience_value"] * audience + w["freshness"] * fresh
            + w["source_credibility"] * cred)

    activities = activity_hits(story, persona)
    # العمود يأتي من النشاط المطابق إن وُجد — وإلا من مطابقة المصطلحات العامة
    pillar = activities[0]["pillar"] if activities else pillar_of(story, persona)
    # إعلان جهة حكومية = خبر قرارات حكومية أولاً، مهما كثرت كلمات المجال الآخر
    if (_hits(story.text, persona.get("government_watchlist", []))
            and any(a["key"] == "government_decisions" for a in activities)):
        pillar = "government_decisions"
    boost, intersection = leadership_boost(story, persona)
    multiplier = boost * float(learning.get(pillar, 1.0))

    sf = persona.get("saudi_first") or {}
    saudi_note = ""
    if sf.get("enabled", True):
        if activities:
            multiplier *= float(sf.get("activity_match_boost", 1.15))
        if geo <= persona["geography"]["priority"]["global"]:   # لا إشارة سعودية ولا خليجية
            ai_only = bool(activities) and all(a["key"] == "artificial_intelligence" for a in activities)
            if ai_only:
                factor, saudi_note = float(sf.get("global_ai_exemption", 0.8)), \
                    "ذكاء اصطناعي عالمي — يحتاج ربطاً سعودياً"
            elif activities:
                factor, saudi_note = float(sf.get("activity_no_saudi_multiplier", 0.75)), \
                    "مرجع عالمي داخل أنشطتك — اربطه بالسوق السعودي"
            else:
                factor, saudi_note = float(sf.get("no_saudi_signal_multiplier", 0.45)), \
                    "بلا إشارة سعودية ولا نشاط من أنشطتك"
            multiplier *= factor
        if is_arabic(story.title):
            multiplier *= float(sf.get("arabic_source_boost", 1.08))

    total = round(min(100.0, base * multiplier), 1)

    story.scores = {"total": total, "base": round(base, 1), "personal_interest": round(interest, 2),
                    "business_relevance": round(business, 2), "saudi_gcc": round(geo, 2),
                    "strategic": round(strategic, 2), "audience_value": round(audience, 2),
                    "freshness": round(fresh, 2), "credibility": round(cred, 2),
                    "multiplier": round(multiplier, 2)}
    story.meta.update({"pillar": pillar, "pillars": pillars_ranked(story)[:3],
                       "activities": [a["label"] for a in activities],
                       "activity_keys": [a["key"] for a in activities],
                       "saudi_note": saudi_note, "arabic": is_arabic(story.title),
                       "region": region, "domains": domains,
                       "interest_hits": interest_hits[:8], "intersection": intersection})
    return story


# ────────────────── تجميع المكرر والتحقق (§21، §22) ──────────────────

STOPWORDS = {"the", "and", "for", "with", "from", "that", "this", "into", "after", "over", "its",
             "new", "says", "said", "will", "has", "have", "are", "was", "were", "amid", "than",
             "على", "من", "في", "عن", "الى", "الي", "مع", "بعد", "بين", "هذا", "التي", "الذي", "قد"}


def _stem(token: str) -> str:
    """جذر خفيف يوحّد صيغ العناوين: backed/backs → back، raises → raise."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > 4 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> set:
    raw = re.findall(r"[\w؀-ۿ]+", normalize(text))
    return {_stem(t) for t in raw if len(t) > 2 and t not in STOPWORDS}


def similarity(a: str, b: str) -> float:
    """تشابه العناوين = مزيج جاكارد (يعاقب الاختلاف) والتغطية (يلتقط إعادة الصياغة)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    shared = ta & tb
    if len(shared) < 2:
        return 0.0
    jaccard = len(shared) / len(ta | tb)
    overlap = len(shared) / min(len(ta), len(tb))
    return round(0.5 * jaccard + 0.5 * overlap, 3)


def passes_activity_filter(story: Story, persona: dict) -> bool:
    """عند تفعيل require_activity_match لا يدخل خط الإنتاج إلا ما يقع داخل الأنشطة الستة."""
    sf = persona.get("saudi_first") or {}
    if not sf.get("require_activity_match"):
        return True
    return bool(story.meta.get("activity_keys"))


def cluster_stories(stories: list, persona: dict) -> list:
    """يجمع الروايات المتعددة للحدث الواحد في عنقود قصة واحد (§21)."""
    threshold = persona["thresholds"]["duplicate_similarity"]
    clusters: list = []
    for story in sorted(stories, key=lambda s: -s.scores.get("total", 0)):
        for cluster in clusters:
            if (similarity(story.title, cluster["primary"].title) >= threshold
                    and len(_tokens(story.title) & _tokens(cluster["primary"].title)) >= 3):
                cluster["supporting"].append(story)
                break
        else:
            clusters.append({"primary": story, "supporting": []})
    for c in clusters:
        members = [c["primary"]] + c["supporting"]
        # المصدر الأعلى مصداقية يصبح المرجع الأساسي للحقائق
        c["best_source"] = max(members, key=lambda s: credibility_score(s, persona))
        c["source_count"] = len(members)
        c["fact_confidence"] = fact_confidence(c, persona)
    return clusters


NUMBER_RE = re.compile(r"\d[\d,.]*\s?(?:%|billion|million|مليار|مليون)?")


def fact_confidence(cluster: dict, persona: dict) -> float:
    """§22: ثقة الحقائق = مصداقية أفضل مصدر + تأكيد مصادر مستقلة + اتساق الأرقام."""
    members = [cluster["primary"]] + cluster["supporting"]
    best = credibility_score(cluster["best_source"], persona)
    corroboration = min(0.2, 0.1 * (len({m.source for m in members}) - 1))
    numbers = [set(NUMBER_RE.findall(m.text)) for m in members if NUMBER_RE.search(m.text)]
    conflict = 0.0
    if len(numbers) > 1:
        shared = set.intersection(*numbers)
        conflict = 0.0 if shared else 0.15   # أرقام متعارضة بين المصادر = خصم
    return round(max(0.0, min(1.0, 0.85 * best + corroboration - conflict)), 2)


# ────────────────── اكتشاف الاتجاهات والفرص (§45، §46) ──────────────────

def detect_trends(clusters: list, persona: dict, min_stories: int = 3) -> list:
    """اتجاه = عدة قصص مستقلة تشير إلى الاتجاه نفسه خلال النافذة الزمنية."""
    buckets: dict = {}
    for c in clusters:
        key = c["primary"].meta.get("pillar", "ai_technology")
        buckets.setdefault(key, []).append(c)
    trends = []
    for pillar, group in buckets.items():
        if len(group) >= min_stories:
            trends.append({
                "pillar": pillar,
                "story_count": len(group),
                "avg_score": round(sum(c["primary"].scores["total"] for c in group) / len(group), 1),
                "headline": f"Trend detected: تسارع في {pillar} — {len(group)} تطورات مستقلة هذا الأسبوع",
                "stories": [c["primary"].title for c in group[:5]],
            })
    return sorted(trends, key=lambda t: -t["story_count"])


OPPORTUNITY_RULES = [
    ("bassir_feature", ["ai monitoring", "computer vision", "quantity takeoff", "ai estimation",
                        "erp", "copilot", "digital twin", "bim automation", "cash flow", "forecast"],
     "ميزة محتملة داخل بصير"),
    ("partnership", ["partnership", "reseller", "integration", "distributor", "شراكة"],
     "شراكة أو تكامل محتمل"),
    ("investment_theme", ["raises", "funding round", "series ", "valuation", "تمويل", "استثمار"],
     "أطروحة استثمارية محتملة"),
    ("competitive_intel", ["launches", "expands to saudi", "enters the middle east", "riyadh office",
                           "يفتتح", "يدخل السوق السعودي"],
     "معلومة تنافسية — لاعب يقترب من السوق"),
]


def detect_opportunities(story: Story) -> list:
    """§45: القصة ليست محتوى فقط — قد تكون فرصة عمل."""
    out = []
    for kind, terms, label in OPPORTUNITY_RULES:
        if _hits(story.text, terms):
            out.append({"type": kind, "label": label})
    return out


# ────────────────── الاعتماد والسلامة (§34-37) ──────────────────

FIRST_PERSON_CLAIM = ["في شركتي", "طبقنا", "نفذنا في", "عملائي", "i implemented", "in my company",
                      "we deployed", "my client"]


def classify_approval(text: str, persona: dict, fact_conf: float = 1.0) -> tuple[str, list]:
    """§37: يعيد (green|yellow|red, الأسباب). الأحمر لا يُنشر آلياً أبداً."""
    safety, t = persona["safety"], normalize(text)
    reasons = []

    red = _hits(t, safety["red_flag_terms"])
    if red:
        reasons.append(f"مصطلحات حساسة: {', '.join(map(str, red[:4]))}")
    claims = _hits(t, FIRST_PERSON_CLAIM)
    if claims:
        reasons.append("ادعاء تجربة شخصية يحتاج تحققاً من facts.yml")
    th = persona["thresholds"]
    if fact_conf < th["fact_confidence_red"]:
        reasons.append(f"ثقة الحقائق متدنية ({fact_conf}) — مصدر واحد ضعيف أو أرقام متعارضة")
    if reasons:
        return "red", reasons

    yellow = _hits(t, safety["yellow_flag_terms"])
    if yellow:
        reasons.append(f"رأي أو توقع: {', '.join(map(str, yellow[:4]))}")
    if fact_conf < th["fact_confidence_autopublish"]:
        reasons.append(f"ثقة الحقائق دون عتبة النشر الآلي ({fact_conf}) — تحقّق من المصدر")
    return ("yellow", reasons) if reasons else ("green", [])


def violates_personal_experience_rule(text: str, facts: dict) -> bool:
    """§34: ادعاء تجربة شخصية غير مذكور في ملف الحقائق."""
    t = normalize(text)
    if not _hits(t, FIRST_PERSON_CLAIM):
        return False
    known = normalize(yaml.dump(facts, allow_unicode=True))
    ventures = [v.get("name", "") for v in facts.get("ventures", {}).get("items", [])]
    return not any(normalize(v) in t for v in ventures if v) and not any(
        w in known for w in list(_tokens(t))[:0])


# ────────────────── مزيج المحتوى وذاكرته (§26، §43) ──────────────────

def mix_deficit(published_counts: dict, persona: dict) -> list:
    """يرتّب الأعمدة حسب الأبعد عن حصته المستهدفة — لضبط المزيج تلقائياً."""
    pillars, total = persona["content_pillars"], max(1, sum(published_counts.values()))
    gaps = []
    for name, spec in pillars.items():
        actual = published_counts.get(name, 0) / total
        gaps.append((round(spec["share"] - actual, 3), name))
    return [name for gap, name in sorted(gaps, reverse=True)]


def is_repeat(text: str, previous: list, threshold: float = 0.62) -> bool:
    """§43: يمنع إعادة إنتاج منشور سابق بالحجة أو الخطّاف نفسه."""
    return any(similarity(text[:400], prev[:400]) >= threshold for prev in previous)


# ────────────────── بناء التعليمات للنموذج ──────────────────

def voice_block(voice: dict, max_chars: int = 3200) -> str:
    """كتلة التقليد: عيّنات بقلم يحيى + تفضيلات صياغته. فارغة إن لم يُعبّأ الملف."""
    if not voice.get("samples") and not voice.get("prefs"):
        return ""

    parts = []
    if voice.get("samples"):
        chunks, budget = [], max_chars
        for s in voice["samples"]:
            body = s["text"][:900]
            if budget - len(body) < 0:
                break
            budget -= len(body)
            chunks.append(f"— {s['title']}:\n{body}")
        parts.append(
            "عيّنات بقلم يحيى نفسه (هذه مرجع الأسلوب لا مرجع المعلومات — لا تقتبس وقائعها):\n\n"
            + "\n\n".join(chunks)
            + "\n\nقلّد إيقاع هذه النصوص: طول الجملة، المفردات، طريقة الفتح والختم، ودرجة الرسمية."
            " لا تنسخ عباراتها.")

    p = voice.get("prefs") or {}
    if p:
        lines = []
        pairs = (("sentence_length", "طول الجملة"), ("formality", "درجة الرسمية"),
                 ("dialect_touch", "اللهجة"), ("openings", "الافتتاح"), ("endings", "الختام"),
                 ("emoji", "الإيموجي"), ("exclamation_marks", "علامات التعجب"))
        for key, label in pairs:
            if p.get(key):
                lines.append(f"{label}: {p[key]}")
        if p.get("avoid_words"):
            lines.append("كلمات ممنوعة نهائياً: " + "، ".join(map(str, p["avoid_words"])))
        if p.get("signature_phrases"):
            lines.append("عبارات تميّزه (استخدمها بتحفّظ): " + "، ".join(map(str, p["signature_phrases"])))
        if lines:
            parts.append("تفضيلات الصياغة الملزمة:\n" + "\n".join(f"  • {x}" for x in lines))
    return "\n\n".join(parts)


def build_system_prompt(persona: dict, facts: dict, language: str = "ar",
                        voice: dict | None = None) -> str:
    v, s = persona["voice"], persona["safety"]
    lang_rule = v["arabic"] if language == "ar" else v["english"]
    voice = voice if voice is not None else load_voice()
    vb = voice_block(voice)
    voice_section = f"\n\n{vb}\n" if vb else ""
    return f"""أنت محرّك قيادة فكر رقمي لـ {persona['identity']['name_ar']} ({persona['identity']['name_en']}).

التموضع: {persona['identity']['positioning']}
لا تقدّمه أبداً كـ: {' أو '.join(persona['identity']['not_positioned_as'])}.

الصوت: {', '.join(v['traits'])}.
ممنوع أن يبدو النص كـ: {', '.join(v['never'])}.
اللغة: {lang_rule}

قواعد لا تُكسر:
1. قاعدة الأصالة (§33): {s['originality_rule']}. لا تلخيص حرفي لمقال.
2. قاعدة التجربة الشخصية (§34): {s['personal_experience_rule']}.
3. قاعدة الرأي (§35): {s['opinion_rule']}. وسم التوقعات صراحةً كتوقع لا كحقيقة.
4. السرية (§36): لا تذكر إطلاقاً: {'، '.join(s['never_expose'])}.
5. الأرقام والوقائع الشخصية تُؤخذ حصراً من ملف الحقائق المرفق — يُمنع اختراع أي رقم أو إنجاز.
6. كل منشور مهم يحمل طبقة رؤية تجيب عن أحد أسئلة: {' | '.join(persona['insight_questions'][:4])}
7. اربط التطور العالمي بالسوق السعودي/الخليجي كلما كان الربط حقيقياً لا متكلفاً.

اختبار الجودة قبل الإخراج (§50): {' '.join(persona['quality_gate'])}
المبدأ الحاكم: {persona['governing_principle']}{voice_section}"""


# ────────────────────────── اختبار ذاتي ──────────────────────────

def _self_test() -> int:
    persona, now = load_persona(), datetime.now(timezone.utc)
    samples = [
        Story(title="Saudi PIF backs AI construction monitoring startup with $40 million to expand in Riyadh",
              summary="The funding round targets computer vision progress tracking for contractors under Vision 2030.",
              source="argaam", source_type="major_international_publication", published=now),
        Story(title="Local cafe launches new seasonal drink",
              summary="A limited edition beverage.", source="blog", source_type="unknown_website", published=now),
    ]
    duplicate = Story(title="PIF backs AI construction monitoring startup in Riyadh with $40m round",
                      summary="Contractors adopt computer vision under Vision 2030.",
                      source="arab news", source_type="major_international_publication", published=now)
    for s in samples + [duplicate]:
        score_story(s, persona, now)
    high, low = samples[0].scores["total"], samples[1].scores["total"]
    clusters = cluster_stories(samples + [duplicate], persona)
    level, reasons = classify_approval("أتوقع أن يصبح هذا معياراً خلال ثلاث سنوات", persona, 1.0)
    checks = [
        ("قصة ذات صلة تتجاوز عتبة خط الإنتاج", high >= persona["thresholds"]["pipeline_entry"]),
        ("قصة غير ذات صلة تبقى دون العتبة", low < persona["thresholds"]["pipeline_entry"]),
        ("الأعمدة المستنتجة تشمل الإنشاءات والذكاء الاصطناعي",
         {"construction_projects", "ai_technology"} <= set(samples[0].meta["pillars"])),
        ("المنطقة سعودية", samples[0].meta["region"] == "saudi_arabia"),
        ("التجميع أنتج عنقودين", len(clusters) == 2),
        ("الروايتان لنفس الحدث اندمجتا", max(c["source_count"] for c in clusters) == 2),
        ("التوقع يُصنَّف أصفر", level == "yellow"),
        ("المالي الحساس يُصنَّف أحمر", classify_approval("إيرادات الشركة وأرباحها", persona)[0] == "red"),
        ("التشابه يكتشف التكرار", similarity("AI construction monitoring in Riyadh",
                                              "AI construction monitoring startup Riyadh") > 0.5),
        ("مزيج الأعمدة يرتّب النقص", mix_deficit({"ai_technology": 10}, persona)[0] != "ai_technology"),
    ]
    for label, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'} — {label}")
    print(f"\nدرجة القصة السعودية: {high} | درجة القصة غير ذات الصلة: {low}")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    import sys
    sys.exit(_self_test() if "--self-test" in sys.argv else print(__doc__) or 0)
