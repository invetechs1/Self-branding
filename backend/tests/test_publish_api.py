"""API test for the manual publish trigger. Uses the real endpoint but a
platform without configured credentials — confirms it fails cleanly (marks
'failed', doesn't crash, doesn't fake success) rather than testing real
network calls."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import settings
from app.db.base import get_session
from app.repositories.persona import PersonaRepository
from app.repositories.posts import PostRepository


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


HEADERS = {"X-API-Key": settings.api_key}


def _approved_draft(db_session, *, platform="linkedin_post"):
    PersonaRepository(db_session).upsert_pillar(
        key="ai_technology", label_ar="الذكاء الاصطناعي والتقنية", label_en="AI & Technology",
        target_share=0.30)
    db_session.flush()
    post = PostRepository(db_session).create_draft(
        platform=platform, language="en", pillar="ai_technology", content_type="news_insight",
        hook="A hook", body="A body worth publishing.", approval_level="green",
        review_notes=None, fact_confidence=0.9, relevance=80.0,
    )
    post.status = "approved"
    db_session.flush()
    return post


def test_publish_endpoint_requires_approved_status(client, db_session):
    post = PostRepository(db_session).create_draft(
        platform="linkedin_post", language="en", pillar=None, content_type="news_insight",
        hook="h", body="b", approval_level="green", review_notes=None,
        fact_confidence=0.9, relevance=80.0,
    )
    db_session.flush()
    resp = client.post(f"/drafts/{post.id}/publish", headers=HEADERS)
    assert resp.status_code == 400


def test_publish_endpoint_fails_cleanly_without_configured_credentials(client, db_session, monkeypatch):
    # Force-blank credentials regardless of the developer's local .env — this
    # test must NEVER be able to trigger a real network call to LinkedIn/X.
    monkeypatch.setattr(settings, "linkedin_access_token", "")
    monkeypatch.setattr(settings, "linkedin_person_urn", "")
    post = _approved_draft(db_session, platform="linkedin_post")
    resp = client.post(f"/drafts/{post.id}/publish", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "publish failed" in (body["review_notes"] or "")


def test_publish_endpoint_manual_platform_schedules(client, db_session):
    post = _approved_draft(db_session, platform="instagram")
    resp = client.post(f"/drafts/{post.id}/publish", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "scheduled"
