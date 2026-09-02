"""Clustering Agent tests — brief § 15's core rule: one event = one cluster,
at most one content opportunity. Mirrors ``persona.py --self-test``'s clustering
assertions plus additional coverage of fact-confidence conflict detection."""

from app.domain.clustering import cluster_articles, is_repeat
from app.domain.models import Article, utcnow
from app.domain.scoring import score_article


def test_two_reports_of_the_same_event_merge_into_one_cluster(persona):
    now = utcnow()
    original = Article(
        title="Saudi PIF backs AI construction monitoring startup with $40 million to expand in Riyadh",
        summary="The funding round targets computer vision progress tracking for contractors under Vision 2030.",
        source="argaam", source_type="major_international_publication", published=now,
    )
    duplicate = Article(
        title="PIF backs AI construction monitoring startup in Riyadh with $40m round",
        summary="Contractors adopt computer vision under Vision 2030.",
        source="arab news", source_type="major_international_publication", published=now,
    )
    unrelated = Article(title="Local cafe launches new seasonal drink", summary="A limited edition beverage.",
                        source="blog", source_type="unknown_website", published=now)

    for a in (original, duplicate, unrelated):
        score_article(a, persona, now)

    clusters = cluster_articles([original, duplicate, unrelated], persona)

    assert len(clusters) == 2
    assert max(c.source_count for c in clusters) == 2


def test_fact_confidence_drops_on_conflicting_numbers(persona):
    now = utcnow()
    a = Article(title="Startup raises $40 million funding round", summary="",
               source="a", source_type="major_international_publication", published=now)
    b = Article(title="Startup raises $60 million funding round", summary="",
               source="b", source_type="major_international_publication", published=now)
    score_article(a, persona, now)
    score_article(b, persona, now)
    clusters = cluster_articles([a, b], persona)
    merged = [c for c in clusters if c.source_count == 2]
    assert merged, "expected the two headlines to merge into one cluster"
    # a lone conflicting-number cluster should not reach the highest confidence band
    assert merged[0].fact_confidence < 0.85


def test_similarity_detects_rephrased_headline():
    from app.domain.text import similarity
    assert similarity("AI construction monitoring in Riyadh",
                      "AI construction monitoring startup Riyadh") > 0.5


def test_is_repeat_flags_near_duplicate_content():
    previous = ["This is a long piece about AI adoption in Saudi construction firms this year and beyond."]
    same_argument = "This is a long piece about AI adoption in Saudi construction firms this year and beyond, expanded."
    different = "A completely unrelated post about logistics fleet productivity metrics."
    assert is_repeat(same_argument, previous)
    assert not is_repeat(different, previous)
