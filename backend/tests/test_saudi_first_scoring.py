"""Saudi-first ranking — the policy the client asked for, ported from
``automation/persona.py`` so backend and CLI rank identically.

Before this port the live engine filtered out every Saudi story in these cases
(all scored 37-51 against a pipeline_entry of 55) while an English AI story
scored 78 — exactly the complaint that triggered the retune. Each test below
pins one mechanism that fixes that.
"""

from datetime import timedelta

from app.domain.models import Article, utcnow
from app.domain.scoring import activity_hits, score_article
from app.domain.text import hits, normalize


def _article(title, summary="", source_type="industry_publication", hours=5, meta=None):
    return Article(title=title, summary=summary, source="t", source_type=source_type,
                   published=utcnow() - timedelta(hours=hours), meta=meta or {})


# ── Arabic matching: prepositions and articles glued to the word ──

def test_attached_preposition_still_matches_keyword():
    assert hits(normalize("ترسية مشاريع بالرياض"), ["الرياض"])
    assert hits(normalize("للمقاولين مهلة جديدة"), ["مقاول"])
    assert hits(normalize("والمقاولات تنمو"), ["مقاولات"])


def test_similar_word_does_not_false_match():
    assert hits(normalize("بطولة رياضة كرة القدم"), ["الرياض"]) == []


# ── The six declared activities ──

def test_activities_detected_and_ranked_by_strength(persona):
    article = _article("وزارة الموارد البشرية تصدر قراراً وزارياً بلائحة تنفيذية وتعميماً على المنشآت")
    acts = activity_hits(article, persona)
    assert acts and acts[0]["key"] == "government_decisions"


def test_activity_counts_as_declared_interest(persona):
    """An Arabic ministry decision names no interest-graph term; without this it scored 0."""
    article = score_article(
        _article("التأمينات الاجتماعية تعدّل آلية احتساب اشتراكات العاملين في القطاع الخاص",
                 "تطبيق تدريجي.", "official_government"), persona, utcnow())
    assert article.scores["personal_interest"] > 0


# ── Geography: who counts as Saudi ──

def test_government_body_is_a_saudi_signal(persona):
    article = score_article(
        _article("وزارة الموارد البشرية تُلزم منشآت المقاولات بتوثيق عقود العمالة عبر منصة قوى",
                 "غرامات عند المخالفة.", "official_government", 4), persona, utcnow())
    assert article.meta["region"] == "saudi_arabia"


def test_topic_watchlist_words_do_not_fake_a_saudi_story(persona):
    """saudi_watchlist holds topics ("Infrastructure", "Tourism"), not places. Using it for
    geography made any global story look Saudi and silently defeated the whole policy."""
    article = score_article(_article("US infrastructure and tourism spending rises in September",
                                     "Spending in the United States."), persona, utcnow())
    assert article.meta["region"] != "saudi_arabia"


def test_source_region_settles_it_when_the_headline_does_not(persona):
    """A ministry's own news page is Saudi even when the headline never says so."""
    article = score_article(_article("تكريم المنشآت المتميزة في بيئة العمل", "", "official_government",
                                     meta={"feed_region": "saudi_arabia"}), persona, utcnow())
    assert article.meta["region"] == "saudi_arabia"


# ── The Saudi-first policy itself ──

def test_saudi_story_outranks_the_global_reference_in_the_same_activity(persona):
    now = utcnow()
    saudi = score_article(_article("ترسية مشاريع بنية تحتية بالرياض على مقاولين محليين",
                                   "مناقصات ومستخلصات وفق العقد الموحد."), persona, now)
    glob = score_article(_article("Contractors adopt BIM on infrastructure projects",
                                  "Productivity study."), persona, now)
    assert saudi.scores["total"] > glob.scores["total"]


def test_global_noise_is_pushed_below_the_pipeline(persona):
    article = score_article(_article("Global shoe brand announces new sneaker line", "Fashion.",
                                     "unknown_website", 2), persona, utcnow())
    assert article.scores["total"] < persona["thresholds"]["pipeline_entry"]
    assert article.meta["saudi_note"]


def test_global_ai_survives_but_is_flagged_for_a_saudi_angle(persona):
    """AI is one of the six activities, so global AI stays in play — but never as a straight
    reprint: the note tells the writer it needs a Saudi angle."""
    article = score_article(_article("OpenAI launches enterprise AI agent platform for finance teams",
                                     "Automation of approvals worldwide.",
                                     "major_international_publication"), persona, utcnow())
    assert article.scores["total"] >= persona["thresholds"]["pipeline_entry"]
    assert "سعودي" in article.meta["saudi_note"]


def test_four_saudi_stories_all_enter_the_pipeline(persona):
    """The regression that matters: these four were all filtered out before the port."""
    now = utcnow()
    cases = [
        ("وزارة الموارد البشرية تُلزم منشآت المقاولات بتوثيق عقود العمالة عبر منصة قوى",
         "غرامات عند المخالفة.", "official_government"),
        ("التأمينات الاجتماعية تعدّل آلية احتساب اشتراكات العاملين", "تطبيق تدريجي.",
         "official_government"),
        ("ترسية مشاريع بنية تحتية بالرياض على مقاولين محليين", "مناقصات ومستخلصات.",
         "industry_publication"),
        ("أمانة جدة ترصد عيوب تنفيذ وتشققات في مبانٍ حديثة", "مخالفات كود البناء وسلامة العمال.",
         "industry_publication"),
    ]
    threshold = persona["thresholds"]["pipeline_entry"]
    for title, summary, stype in cases:
        article = score_article(_article(title, summary, stype), persona, now)
        assert article.scores["total"] >= threshold, f"{title} -> {article.scores['total']}"


# ── Pillar routing ──

def test_purely_governmental_headline_routes_to_government_decisions(persona):
    article = score_article(
        _article("وزارة الموارد البشرية تصدر قراراً وزارياً بلائحة تنفيذية وتعميماً على المنشآت",
                 "", "official_government"), persona, utcnow())
    assert article.meta["pillar"] == "government_decisions"


def test_article_scraped_from_a_ministry_page_is_a_government_story(persona):
    """Source beats keyword counting: a headline mixing ministry and contracting words
    (e.g. a Qiwa rule aimed at contractors) otherwise routes to construction_projects
    on raw keyword counts. gov_entity is set by the government-page watcher."""
    article = score_article(
        _article("وزارة الموارد البشرية تُلزم منشآت المقاولات بتوثيق عقود العمالة عبر منصة قوى",
                 "", "official_government", meta={"gov_entity": "hrsd"}), persona, utcnow())
    assert article.meta["pillar"] == "government_decisions"


def test_building_defects_route_to_site_quality(persona):
    article = score_article(_article("تشققات وعيوب تنفيذ ورطوبة في واجهات مبنى وأخطاء العزل"),
                            persona, utcnow())
    assert article.meta["pillar"] == "site_quality"


def test_scored_article_exposes_activities_for_the_ui(persona):
    article = score_article(_article("ترسية مشاريع بنية تحتية بالرياض على مقاولين محليين"),
                            persona, utcnow())
    assert article.meta["activities"] and article.meta["activity_keys"]
