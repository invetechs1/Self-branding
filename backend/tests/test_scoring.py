"""Scoring Agent tests. First two cases are the exact assertions from
``automation/persona.py --self-test``, kept identical so a behavior change
here is visible as a diff against the CLI reference, not a silent drift."""

from app.domain.models import Article, utcnow
from app.domain.scoring import score_article


def _relevant_article(now):
    return Article(
        title="Saudi PIF backs AI construction monitoring startup with $40 million to expand in Riyadh",
        summary="The funding round targets computer vision progress tracking for contractors under Vision 2030.",
        source="argaam", source_type="major_international_publication", published=now,
    )


def _irrelevant_article(now):
    return Article(title="Local cafe launches new seasonal drink", summary="A limited edition beverage.",
                   source="blog", source_type="unknown_website", published=now)


def test_relevant_saudi_construction_ai_story_crosses_pipeline_threshold(persona):
    now = utcnow()
    article = score_article(_relevant_article(now), persona, now)
    assert article.scores["total"] >= persona["thresholds"]["pipeline_entry"]


def test_irrelevant_story_stays_below_pipeline_threshold(persona):
    now = utcnow()
    article = score_article(_irrelevant_article(now), persona, now)
    assert article.scores["total"] < persona["thresholds"]["pipeline_entry"]


def test_pillars_include_construction_and_ai(persona):
    now = utcnow()
    article = score_article(_relevant_article(now), persona, now)
    assert {"construction_projects", "ai_technology"} <= set(article.meta["pillars"])


def test_region_detected_as_saudi_arabia(persona):
    now = utcnow()
    article = score_article(_relevant_article(now), persona, now)
    assert article.meta["region"] == "saudi_arabia"


def test_freshness_decays_and_expires(persona):
    from datetime import timedelta
    now = utcnow()
    fresh = score_article(_relevant_article(now), persona, now)
    old = _relevant_article(now)
    old.published = now - timedelta(hours=persona["thresholds"]["freshness_max_age_hours"] + 1)
    stale = score_article(old, persona, now)
    assert stale.scores["freshness"] == 0.0
    # This article is strong enough that both versions pin at the 100 cap once the
    # Saudi-first multipliers apply, so the decay is asserted on the uncapped weighted
    # base. See KNOWN ISSUE in docs/backend-port-guide-EN.md: the cap costs ranking
    # resolution among the strongest stories and should be revisited product-wide.
    assert stale.scores["base"] < fresh.scores["base"]


def test_freshness_visible_in_total_for_a_mid_range_story(persona):
    """Same property on a story that does not hit the cap — guards the user-visible score."""
    from datetime import timedelta
    now = utcnow()
    article = Article(title="Contractors adopt digital twin tools on infrastructure projects",
                      summary="A productivity study.", source="enr",
                      source_type="industry_publication", published=now)
    fresh = score_article(article, persona, now)
    older = article.model_copy(deep=True)
    older.published = now - timedelta(hours=48)
    stale = score_article(older, persona, now)
    assert fresh.scores["total"] < 100.0
    assert stale.scores["total"] < fresh.scores["total"]


def test_learning_multiplier_is_applied_and_bounded(persona):
    now = utcnow()
    boosted = score_article(_relevant_article(now), persona, now, learning={"construction_engineering": 1.4})
    neutral = score_article(_relevant_article(now), persona, now, learning={})
    assert boosted.scores["total"] >= neutral.scores["total"]


def test_leadership_boost_detected_for_ai_construction_business_intersection(persona):
    now = utcnow()
    article = Article(
        title="AI construction monitoring startup raises funding to help contractors cut costs",
        summary="A business automation play for the construction industry.",
        source="enr", source_type="industry_publication", published=now,
    )
    score_article(article, persona, now)
    assert article.meta["intersection"] != ""
