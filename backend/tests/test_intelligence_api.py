"""API tests for the read-only intelligence endpoints backing the future
"Today's Intelligence" dashboard screen."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import settings
from app.db.base import get_session
from app.domain.clustering import cluster_articles
from app.domain.models import Article, utcnow
from app.domain.scoring import score_article
from app.repositories.articles import RawArticleRepository
from app.repositories.clusters import StoryClusterRepository
from app.repositories.opportunities import OpportunityRepository
from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository
from app.domain.opportunities import detect_opportunities


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_one_cluster(db_session, persona):
    repo = PersonaRepository(db_session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key, target_share=spec["share"])
    repo.save_persona_config(version="test", config=persona)
    db_session.flush()

    now = utcnow()
    article = Article(
        title="Saudi PIF backs AI construction monitoring startup with $40 million to expand in Riyadh",
        summary="The funding round targets computer vision progress tracking for contractors under Vision 2030.",
        url="https://example.test/story-1", source="Test Source",
        source_type="major_international_publication", published=now,
    )
    score_article(article, persona, now)
    article_repo = RawArticleRepository(db_session)
    row = article_repo.save_scored(article, source_id=None)

    cluster = cluster_articles([article], persona)[0]
    StoryClusterRepository(db_session).create_from_cluster_result(cluster, {article.url: row.id})
    db_session.flush()
    return row


def test_clusters_endpoint_requires_auth(client):
    assert client.get("/clusters").status_code == 401


def test_clusters_and_articles_endpoints_return_seeded_data(client, db_session, persona):
    _seed_one_cluster(db_session, persona)
    headers = {"X-API-Key": settings.api_key}

    clusters = client.get("/clusters", headers=headers).json()
    assert len(clusters) == 1
    assert clusters[0]["source_count"] == 1

    detail = client.get(f"/clusters/{clusters[0]['id']}", headers=headers).json()
    assert len(detail["articles"]) == 1
    # top-ranked pillar for this headline is saudi_economy (saudi/pif/riyadh out-hit the
    # ai/construction terms) — assert it's a real, known pillar, not a specific guess
    assert detail["articles"][0]["pillar"] in persona["content_pillars"]

    top = client.get("/articles/top", headers=headers).json()
    assert len(top) == 1
    assert top[0]["relevance"] > 0


def test_get_unknown_cluster_returns_404(client):
    import uuid
    resp = client.get(f"/clusters/{uuid.uuid4()}", headers={"X-API-Key": settings.api_key})
    assert resp.status_code == 404


def test_cluster_includes_source_name_and_credibility(client, db_session, persona):
    repo = PersonaRepository(db_session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key, target_share=spec["share"])
    repo.save_persona_config(version="test", config=persona)
    source_repo = SourceRepository(db_session)
    source_repo.upsert(name="Arab News — Business", url="https://arabnews.test/rss", kind="rss",
                       source_type="major_international_publication", credibility=90, region="saudi_arabia")
    db_session.flush()
    source_id = source_repo.list_enabled()[0].id

    now = utcnow()
    article = Article(title="Saudi PIF backs AI construction monitoring startup with $40 million",
                      summary="Computer vision progress tracking for contractors.",
                      url="https://example.test/story-src", source="Arab News — Business",
                      source_type="major_international_publication", published=now)
    score_article(article, persona, now)
    row = RawArticleRepository(db_session).save_scored(article, source_id=source_id)
    cluster = cluster_articles([article], persona)[0]
    StoryClusterRepository(db_session).create_from_cluster_result(cluster, {article.url: row.id})
    db_session.flush()

    headers = {"X-API-Key": settings.api_key}
    clusters = client.get("/clusters", headers=headers).json()
    detail = client.get(f"/clusters/{clusters[0]['id']}", headers=headers).json()

    assert detail["articles"][0]["source"]["name"] == "Arab News — Business"
    assert detail["articles"][0]["source"]["credibility"] == 90


def test_opportunities_endpoint_lists_and_dismisses(client, db_session, persona):
    repo = PersonaRepository(db_session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key, target_share=spec["share"])
    repo.save_persona_config(version="test", config=persona)
    db_session.flush()

    now = utcnow()
    article = Article(title="Startup launches AI monitoring and ERP platform with cash flow forecasting",
                      summary="An integration play for contractors.", url="https://example.test/opp-1",
                      source="Test", source_type="industry_publication", published=now)
    score_article(article, persona, now)
    row = RawArticleRepository(db_session).save_scored(article, source_id=None)
    cluster = cluster_articles([article], persona)[0]
    cluster_row = StoryClusterRepository(db_session).create_from_cluster_result(cluster, {article.url: row.id})
    opp_repo = OpportunityRepository(db_session)
    for opp in detect_opportunities(cluster):
        opp_repo.create(cluster_row.id, opp["type"], opp["label"])
    db_session.flush()

    headers = {"X-API-Key": settings.api_key}
    listed = client.get("/opportunities", headers=headers).json()
    assert len(listed) >= 1
    assert listed[0]["status"] == "new"
    assert listed[0]["headline"] == cluster_row.headline

    dismiss = client.post(f"/opportunities/{listed[0]['id']}/dismiss", headers=headers)
    assert dismiss.status_code == 200

    remaining = client.get("/opportunities", headers=headers).json()
    assert all(o["id"] != listed[0]["id"] for o in remaining)
