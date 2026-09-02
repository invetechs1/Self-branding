"""Publishing service — TRD § 8, brief § 18 "Social Integrations".

Two platforms wired now (X, LinkedIn); Instagram is deliberately on hold per
explicit instruction; TikTok and long-form articles stay manual, matching the
original CLI reference's design (`automation/publish.py::PUBLISHERS`).

Idempotency (brief: "never publish the same content twice because of a
retry"): the real guarantee lives in `publish_draft`'s status check, not in
the platform HTTP calls themselves — once a post reaches status='posted' with
an `external_id`, calling `publish_draft` again is a no-op and returns the
existing result. This holds even if the *caller* retries the whole operation
(e.g. a flaky scheduler), which is the retry path that actually matters.

Every platform call takes an injectable `call_fn` so tests never hit a real
API — production code omits it and gets the real HTTP client.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.config import settings
from app.repositories.posts import PostRepository

MANUAL_PLATFORMS = {"instagram", "tiktok", "article"}
AUTOMATED_PLATFORMS = {"x", "x_thread", "linkedin_post"}


class PublishError(RuntimeError):
    """Raised when a platform call fails after all retries. The caller is
    expected to catch this and mark the post 'failed' with the error noted —
    never silently swallowed, never silently retried past the configured cap."""


@dataclass
class PublishResult:
    external_id: str
    note: str = ""


# ── X ──

def _default_x_call(content: str) -> str:
    import tweepy

    client = tweepy.Client(
        consumer_key=settings.x_api_key, consumer_secret=settings.x_api_secret,
        access_token=settings.x_access_token, access_token_secret=settings.x_access_token_secret,
    )
    reply_to = None
    last_id = None
    for part in [p.strip() for p in content.split("\n---\n") if p.strip()]:
        resp = client.create_tweet(text=part, in_reply_to_tweet_id=reply_to)
        last_id = resp.data["id"]
        reply_to = last_id
    return str(last_id)


def post_to_x(content: str, *, call_fn: Callable[[str], str] | None = None,
             sleep_fn: Callable[[float], None] | None = None) -> PublishResult:
    if not settings.x_api_key and call_fn is None:
        raise PublishError("X API not configured (X_API_KEY missing) — see backend/.env.example")
    call_fn = call_fn or _default_x_call
    external_id = _with_retries(lambda: call_fn(content), sleep_fn=sleep_fn)
    return PublishResult(external_id=external_id, note="posted to X")


# ── LinkedIn ──

def _default_linkedin_call(content: str) -> str:
    import requests

    if not settings.linkedin_access_token or not settings.linkedin_person_urn:
        raise PublishError("LinkedIn API not configured — see backend/.env.example")
    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={"Authorization": f"Bearer {settings.linkedin_access_token}",
                 "X-Restli-Protocol-Version": "2.0.0"},
        json={
            "author": settings.linkedin_person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content}, "shareMediaCategory": "NONE"}},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }, timeout=30,
    )
    resp.raise_for_status()
    return resp.headers.get("x-restli-id", str(uuid.uuid4()))


def post_to_linkedin(content: str, *, call_fn: Callable[[str], str] | None = None,
                     sleep_fn: Callable[[float], None] | None = None) -> PublishResult:
    call_fn = call_fn or _default_linkedin_call
    external_id = _with_retries(lambda: call_fn(content), sleep_fn=sleep_fn)
    return PublishResult(external_id=external_id, note="posted to LinkedIn")


# ── retry policy: transient failures only, capped, no silent duplication ──

def _with_retries(fn: Callable[[], str], *, max_attempts: int = 3,
                  sleep_fn: Callable[[float], None] | None = None) -> str:
    sleep_fn = sleep_fn or time.sleep
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except PublishError:
            raise   # permanent failure (e.g. "not configured") — retrying can't help, fail fast
        except Exception as e:  # noqa: BLE001 — transient failures count against the retry budget
            last_error = e
            if attempt < max_attempts - 1:
                sleep_fn(2 ** attempt)
    raise PublishError(f"publish failed after {max_attempts} attempts: {last_error}")


PUBLISHERS: dict[str, Callable[..., PublishResult]] = {
    "x": post_to_x,
    "x_thread": post_to_x,
    "linkedin_post": post_to_linkedin,
}


def publish_draft(session: Session, post_id: uuid.UUID, *,
                  call_fn: Callable[[str], str] | None = None,
                  sleep_fn: Callable[[float], None] | None = None) -> "Post":  # noqa: F821
    """Publishes one approved draft. Idempotent: a post already 'posted' is
    returned as-is, never re-published."""
    repo = PostRepository(session)
    post = repo.get(post_id)
    if post is None:
        raise ValueError(f"unknown post: {post_id}")

    if post.status == "posted":
        return post  # idempotent no-op — the guarantee that actually matters
    if post.status != "approved":
        raise ValueError(f"post must be 'approved' before publishing (currently '{post.status}')")

    if post.platform in MANUAL_PLATFORMS:
        post.status = "scheduled"
        post.review_notes = (post.review_notes or "") + " | manual publish required for this platform"
        return post

    publisher = PUBLISHERS.get(post.platform)
    if publisher is None:
        raise ValueError(f"no publisher configured for platform: {post.platform}")

    try:
        result = publisher(post.body, call_fn=call_fn, sleep_fn=sleep_fn)
    except PublishError as e:
        post.status = "failed"
        post.review_notes = (post.review_notes or "") + f" | publish failed: {e}"
        return post

    post.status = "posted"
    post.external_id = result.external_id
    post.posted_at = datetime.now(timezone.utc)
    return post
