"""Publishing service tests — no real network calls, ever. Covers brief § 18's
idempotency requirement ("never publish the same content twice because of a
retry") and the retry/backoff policy."""

import pytest

from app.repositories.persona import PersonaRepository
from app.repositories.posts import PostRepository
from app.services.publishing import PublishError, publish_draft


def _seed_pillar(db_session):
    PersonaRepository(db_session).upsert_pillar(
        key="ai_technology", label_ar="الذكاء الاصطناعي والتقنية", label_en="AI & Technology",
        target_share=0.30)
    db_session.flush()


def _make_post(db_session, *, platform="linkedin_post", status="approved"):
    _seed_pillar(db_session)
    post = PostRepository(db_session).create_draft(
        platform=platform, language="en", pillar="ai_technology", content_type="news_insight",
        hook="A hook", body="A body worth publishing.", approval_level="green",
        review_notes=None, fact_confidence=0.9, relevance=80.0,
    )
    post.status = status
    db_session.flush()
    return post


def test_publish_linkedin_success(db_session):
    post = _make_post(db_session, platform="linkedin_post")
    calls = []

    def fake_call(content):
        calls.append(content)
        return "urn:li:share:123"

    result = publish_draft(db_session, post.id, call_fn=fake_call)

    assert result.status == "posted"
    assert result.external_id == "urn:li:share:123"
    assert result.posted_at is not None
    assert len(calls) == 1


def test_publish_x_thread_splits_on_separator(db_session):
    post = _make_post(db_session, platform="x_thread")
    post.body = "First tweet\n---\nSecond tweet"
    db_session.flush()

    parts_seen = []

    def fake_call(content):
        parts_seen.append(content)
        return "tweet_id_2"

    result = publish_draft(db_session, post.id, call_fn=fake_call)
    assert result.status == "posted"
    assert result.external_id == "tweet_id_2"


def test_publish_is_idempotent_second_call_does_not_republish(db_session):
    post = _make_post(db_session, platform="linkedin_post")
    calls = []

    def fake_call(content):
        calls.append(content)
        return "urn:li:share:once"

    first = publish_draft(db_session, post.id, call_fn=fake_call)
    second = publish_draft(db_session, first.id, call_fn=fake_call)

    assert first.external_id == second.external_id == "urn:li:share:once"
    assert len(calls) == 1   # the platform was only ever called once


def test_publish_requires_approved_status(db_session):
    post = _make_post(db_session, platform="linkedin_post", status="pending_review")
    with pytest.raises(ValueError, match="approved"):
        publish_draft(db_session, post.id, call_fn=lambda content: "x")


def test_publish_manual_platform_schedules_instead_of_posting(db_session):
    post = _make_post(db_session, platform="instagram")
    called = {"n": 0}

    def fake_call(content):
        called["n"] += 1
        return "should-not-be-called"

    result = publish_draft(db_session, post.id, call_fn=fake_call)
    assert result.status == "scheduled"
    assert called["n"] == 0


def test_publish_retries_transient_failure_then_succeeds(db_session):
    post = _make_post(db_session, platform="linkedin_post")
    attempts = {"n": 0}

    def flaky_call(content):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise ConnectionError("simulated network blip")
        return "urn:li:share:after-retry"

    result = publish_draft(db_session, post.id, call_fn=flaky_call, sleep_fn=lambda s: None)
    assert result.status == "posted"
    assert result.external_id == "urn:li:share:after-retry"
    assert attempts["n"] == 2


def test_publish_marks_failed_after_exhausting_retries(db_session):
    post = _make_post(db_session, platform="linkedin_post")

    def always_fails(content):
        raise ConnectionError("simulated persistent outage")

    result = publish_draft(db_session, post.id, call_fn=always_fails, sleep_fn=lambda s: None)
    assert result.status == "failed"
    assert "publish failed" in (result.review_notes or "")


def test_publish_unknown_post_raises(db_session):
    import uuid
    with pytest.raises(ValueError, match="unknown post"):
        publish_draft(db_session, uuid.uuid4(), call_fn=lambda content: "x")


def test_failed_post_can_be_retried_and_succeeds(db_session):
    post = _make_post(db_session, platform="linkedin_post")
    publish_draft(db_session, post.id, call_fn=lambda c: (_ for _ in ()).throw(ConnectionError("down")),
                  sleep_fn=lambda s: None)
    assert post.status == "failed"

    result = publish_draft(db_session, post.id, call_fn=lambda c: "urn:li:share:retried")
    assert result.status == "posted"
    assert result.external_id == "urn:li:share:retried"
    assert "publish failed" not in (result.review_notes or "")


def test_permanent_http_error_fails_fast_without_retries(db_session):
    """402/401/403 can't fix themselves in seconds — one attempt, clear reason."""
    post = _make_post(db_session, platform="x")
    attempts = {"n": 0}

    class FakeResponse:
        status_code = 402

    class PaymentRequired(Exception):
        response = FakeResponse()

    def no_credit(content):
        attempts["n"] += 1
        raise PaymentRequired("402 Payment Required")

    result = publish_draft(db_session, post.id, call_fn=no_credit, sleep_fn=lambda s: None)
    assert result.status == "failed"
    assert attempts["n"] == 1
    assert "no credit left" in result.review_notes


def test_repeated_failures_do_not_pile_up_notes(db_session):
    post = _make_post(db_session, platform="linkedin_post")
    boom = lambda c: (_ for _ in ()).throw(ConnectionError("down"))  # noqa: E731
    publish_draft(db_session, post.id, call_fn=boom, sleep_fn=lambda s: None)
    publish_draft(db_session, post.id, call_fn=boom, sleep_fn=lambda s: None)
    assert post.review_notes.count(" | publish failed:") == 1
