"""Opportunity/Trend detection tests (TRD § 45-46)."""

from app.domain.clustering import cluster_articles
from app.domain.models import Article, utcnow
from app.domain.opportunities import detect_opportunities, detect_trends
from app.domain.scoring import score_article
from app.repositories.clusters import StoryClusterRepository
from app.repositories.opportunities import OpportunityRepository
from app.repositories.articles import RawArticleRepository
from app.repositories.persona import PersonaRepository


def test_detect_opportunities_flags_bassir_feature_terms(persona):
    now = utcnow()
    article = Article(title="Startup launches AI monitoring and computer vision platform for contractors",
                      summary="An ERP integration with cash flow forecasting.", source="a",
                      source_type="industry_publication", published=now)
    score_article(article, persona, now)
    cluster = cluster_articles([article], persona)[0]

    opps = detect_opportunities(cluster)
    types = {o["type"] for o in opps}
    assert "bassir_feature" in types


def test_detect_opportunities_returns_empty_for_unrelated_story(persona):
    now = utcnow()
    # deliberately avoids every OPPORTUNITY_RULES term (including generic ones
    # like "launches", which a cafe/product story would otherwise trip)
    article = Article(title="Local weather turns cooler this weekend across the region",
                      summary="A mild cold front brings light rain overnight.",
                      source="blog", source_type="unknown_website", published=now)
    score_article(article, persona, now)
    cluster = cluster_articles([article], persona)[0]

    assert detect_opportunities(cluster) == []


def test_detect_trends_requires_minimum_independent_clusters(persona):
    now = utcnow()
    clusters = []
    for i in range(3):
        article = Article(title=f"AI construction monitoring adoption story number {i}",
                          summary="Contractors adopt computer vision.", source=f"src{i}",
                          source_type="industry_publication", published=now)
        score_article(article, persona, now)
        clusters.append(cluster_articles([article], persona)[0])

    trends = detect_trends(clusters, min_stories=3)
    assert len(trends) == 1
    assert trends[0]["story_count"] == 3


def test_opportunity_repository_persists_and_lists_new(db_session, persona):
    repo = PersonaRepository(db_session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key, target_share=spec["share"])
    db_session.flush()

    now = utcnow()
    article = Article(title="Startup launches AI monitoring and ERP platform for contractors",
                      summary="Cash flow forecasting included.", url="https://example.test/opp",
                      source="a", source_type="industry_publication", published=now)
    score_article(article, persona, now)
    article_row = RawArticleRepository(db_session).save_scored(article, source_id=None)
    cluster = cluster_articles([article], persona)[0]
    cluster_row = StoryClusterRepository(db_session).create_from_cluster_result(
        cluster, {article.url: article_row.id})

    opp_repo = OpportunityRepository(db_session)
    for opp in detect_opportunities(cluster):
        opp_repo.create(cluster_row.id, opp["type"], opp["label"])
    db_session.flush()

    listed = opp_repo.list_new()
    assert len(listed) >= 1
    assert listed[0].status == "new"
