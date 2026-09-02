"""Performance & Learning API tests — including the empty-state (no posts
published yet, matching a real fresh deployment) and the recompute cycle
against real approval/metrics data (never mocked numbers)."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import settings as app_settings
from app.db.base import get_session
from app.db.models import ApprovalDecision, Post
from app.repositories.metrics import MetricsRepository
from app.repositories.persona import PersonaRepository

HEADERS = {"X-API-Key": app_settings.api_key}


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_persona(db_session, persona):
    repo = PersonaRepository(db_session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key, target_share=spec["share"])
    repo.save_persona_config(version="test", config=persona)
    db_session.flush()


def test_summary_on_fresh_install_is_honestly_empty_not_fabricated(client, db_session, persona):
    _seed_persona(db_session, persona)
    resp = client.get("/performance/summary", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["posts_published"] == 0
    assert body["approved"] == 0
    assert body["approval_rate"] is None   # not 0% — genuinely "no data" is different from "0% approval"
    assert body["total_impressions"] == 0
    assert body["platform_performance"] == []
    assert body["learned"] == []


def test_summary_counts_real_posted_posts_and_metrics(client, db_session, persona):
    _seed_persona(db_session, persona)
    post = Post(platform="linkedin_post", language="en", pillar="ai_technology",
               content_type="news_insight", hook="h", body="b", approval_level="green",
               status="posted")
    db_session.add(post)
    db_session.flush()
    MetricsRepository(db_session).record(post.id, impressions=1000, likes=50, comments=10,
                                         shares=5, saves=2, profile_visits=3, followers_gained=1)
    db_session.add(ApprovalDecision(post_id=post.id, decision="approved", decided_by="yahya"))
    db_session.flush()

    resp = client.get("/performance/summary", headers=HEADERS)
    body = resp.json()
    assert body["posts_published"] == 1
    assert body["approved"] == 1
    assert body["approval_rate"] == 1.0
    assert body["total_impressions"] == 1000
    assert body["avg_engagement_rate"] > 0
    assert len(body["platform_performance"]) == 1
    assert body["platform_performance"][0]["platform"] == "linkedin_post"


def test_published_posts_list_joins_metrics(client, db_session, persona):
    _seed_persona(db_session, persona)
    post = Post(platform="x", language="en", pillar="ai_technology", content_type="news_insight",
               hook="hook text", body="b", approval_level="green", status="posted")
    db_session.add(post)
    db_session.flush()
    MetricsRepository(db_session).record(post.id, impressions=500, likes=20, comments=1, shares=1)
    db_session.flush()

    resp = client.get("/performance/posts", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["hook"] == "hook text"
    assert body[0]["impressions"] == 500


def test_recompute_updates_pillar_multipliers_from_real_signals(client, db_session, persona):
    _seed_persona(db_session, persona)

    # 3 posts in ai_technology, all approved, strong engagement -> multiplier should rise
    for i in range(3):
        post = Post(platform="linkedin_post", language="en", pillar="ai_technology",
                   content_type="news_insight", hook=f"h{i}", body="b", approval_level="green",
                   status="posted")
        db_session.add(post)
        db_session.flush()
        MetricsRepository(db_session).record(post.id, impressions=1000, likes=200, comments=50,
                                             shares=30, saves=10, profile_visits=5, followers_gained=5)
        db_session.add(ApprovalDecision(post_id=post.id, decision="approved", decided_by="yahya"))
    # 3 posts in investment, all rejected, no engagement
    for i in range(3):
        post = Post(platform="linkedin_post", language="en", pillar="investment",
                   content_type="news_insight", hook=f"i{i}", body="b", approval_level="green",
                   status="rejected")
        db_session.add(post)
        db_session.flush()
        db_session.add(ApprovalDecision(post_id=post.id, decision="rejected", decided_by="yahya"))
    db_session.flush()

    resp = client.post("/performance/recompute", headers=HEADERS)
    assert resp.status_code == 200
    weights = resp.json()["weights"]
    assert weights["ai_technology"] > weights["investment"]

    pillars_after = client.get("/settings/pillars", headers=HEADERS).json()
    ai = next(p for p in pillars_after if p["key"] == "ai_technology")
    assert ai["multiplier"] == weights["ai_technology"]   # actually persisted, not just returned


def test_recompute_never_pushes_multiplier_outside_bounds(client, db_session, persona):
    _seed_persona(db_session, persona)
    for i in range(10):
        post = Post(platform="linkedin_post", language="en", pillar="ai_technology",
                   content_type="news_insight", hook=f"h{i}", body="b", approval_level="green",
                   status="posted")
        db_session.add(post)
        db_session.flush()
        MetricsRepository(db_session).record(post.id, impressions=1000, likes=900, comments=500,
                                             shares=500, saves=500, profile_visits=500, followers_gained=500)
        db_session.add(ApprovalDecision(post_id=post.id, decision="approved", decided_by="yahya"))
    db_session.flush()

    resp = client.post("/performance/recompute", headers=HEADERS)
    weights = resp.json()["weights"]
    assert 0.7 <= weights["ai_technology"] <= 1.4


def test_performance_endpoints_require_auth(client):
    assert client.get("/performance/summary").status_code == 401
    assert client.post("/performance/recompute").status_code == 401
