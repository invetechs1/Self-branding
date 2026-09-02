"""Drafts & Approval API tests — brief rule 5 ("RED must never auto-publish")
enforced end-to-end through the HTTP layer, not just the repository."""

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


def _make_draft(db_session, *, approval_level="yellow"):
    # posts.pillar is FK-constrained to pillars.key — matches the real seed
    # order (scripts/seed.py always seeds pillars first), not a test artifact.
    PersonaRepository(db_session).upsert_pillar(
        key="ai_technology", label_ar="الذكاء الاصطناعي والتقنية", label_en="AI & Technology",
        target_share=0.30)
    db_session.flush()
    post = PostRepository(db_session).create_draft(
        platform="linkedin_post", language="en", pillar="ai_technology",
        content_type="news_insight", hook="A hook", body="A body worth reviewing.",
        approval_level=approval_level, review_notes=None, fact_confidence=0.9, relevance=80.0,
    )
    db_session.flush()
    return post


def test_list_drafts_requires_auth(client):
    assert client.get("/drafts").status_code == 401


def test_list_and_get_draft(client, db_session):
    post = _make_draft(db_session)
    listing = client.get("/drafts", headers=HEADERS).json()
    assert len(listing) == 1
    assert listing[0]["status"] == "pending_review"

    detail = client.get(f"/drafts/{post.id}", headers=HEADERS).json()
    assert detail["hook"] == "A hook"


def test_approve_draft(client, db_session):
    post = _make_draft(db_session, approval_level="green")
    resp = client.post(f"/drafts/{post.id}/approve", json={}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_approve_red_draft_without_confirmation_is_rejected(client, db_session):
    post = _make_draft(db_session, approval_level="red")
    resp = client.post(f"/drafts/{post.id}/approve", json={}, headers=HEADERS)
    assert resp.status_code == 409

    still_pending = client.get(f"/drafts/{post.id}", headers=HEADERS).json()
    assert still_pending["status"] == "pending_review"


def test_approve_red_draft_with_explicit_confirmation_succeeds(client, db_session):
    post = _make_draft(db_session, approval_level="red")
    resp = client.post(f"/drafts/{post.id}/approve", json={"confirmed_red": True}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_edit_and_approve_draft(client, db_session):
    post = _make_draft(db_session, approval_level="yellow")
    resp = client.post(f"/drafts/{post.id}/edit-approve",
                       json={"body": "An edited, better body."}, headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["body"] == "An edited, better body."
    assert body["status"] == "approved"


def test_reject_draft_with_reason_tags(client, db_session):
    post = _make_draft(db_session)
    resp = client.post(f"/drafts/{post.id}/reject",
                       json={"reason_tags": ["tone", "weak-insight"], "comment": "Not quite right."},
                       headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_rejected_draft_drops_out_of_the_active_queue(client, db_session):
    post = _make_draft(db_session)
    client.post(f"/drafts/{post.id}/reject", json={"reason_tags": ["tone"]}, headers=HEADERS)
    assert client.get("/drafts", headers=HEADERS).json() == []


def test_rejected_draft_is_visible_in_the_rejected_archive_with_its_reason(client, db_session):
    post = _make_draft(db_session)
    client.post(f"/drafts/{post.id}/reject",
               json={"reason_tags": ["tone", "weak-insight"], "comment": "Not quite right."},
               headers=HEADERS)
    listing = client.get("/drafts/rejected", headers=HEADERS).json()
    assert len(listing) == 1
    assert listing[0]["id"] == str(post.id)
    assert listing[0]["status"] == "rejected"
    assert listing[0]["reason_tags"] == ["tone", "weak-insight"]
    assert listing[0]["comment"] == "Not quite right."
    assert listing[0]["rejected_at"] is not None


def test_get_unknown_draft_returns_404(client):
    import uuid
    resp = client.get(f"/drafts/{uuid.uuid4()}", headers=HEADERS)
    assert resp.status_code == 404
