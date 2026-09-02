"""Generation service tests — full agent pipeline against a real DB, all four
LLM calls faked. Verifies the brief's hard rules land in the persisted row:
safety level is deterministic, memory dedup works, red requires explicit
sign-off downstream (tested in test_drafts_api.py)."""

import json

from app.domain.clustering import cluster_articles
from app.domain.models import Article, utcnow
from app.domain.scoring import score_article
from app.repositories.articles import RawArticleRepository
from app.repositories.clusters import StoryClusterRepository
from app.repositories.persona import PersonaRepository
from app.repositories.posts import PostRepository
from app.services.generation import generate_draft_for_cluster, regenerate_draft


def _seed(db_session, persona):
    repo = PersonaRepository(db_session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key, target_share=spec["share"])
    repo.add_knowledge_item("company", "Azoom United Contracting", "Founder and CEO, construction and contracting",
                            is_public=True, source="facts.yml")
    repo.save_persona_config(version="test", config=persona)
    db_session.flush()


def _make_cluster(db_session, persona, title="Saudi PIF backs AI construction monitoring startup with $40 million to expand in Riyadh"):
    now = utcnow()
    article = Article(title=title,
                      summary="The funding round targets computer vision progress tracking for contractors.",
                      url=f"https://example.test/{hash(title)}", source="Test Source",
                      source_type="major_international_publication", published=now)
    score_article(article, persona, now)
    article_repo = RawArticleRepository(db_session)
    row = article_repo.save_scored(article, source_id=None)
    cluster = cluster_articles([article], persona)[0]
    cluster_row = StoryClusterRepository(db_session).create_from_cluster_result(
        cluster, {article.url: row.id})
    db_session.flush()
    return cluster_row.id


def _fake(text):
    return lambda *, model, system, user, max_tokens: text


VERIFY_JSON = json.dumps({"agreed_facts": ["$40 million funding round", "expansion in Riyadh"], "flags": []})
ANGLE_JSON = json.dumps({"angle": "AI opportunity", "why_it_matters": "Direct signal for Bassir's roadmap."})
INSIGHT_JSON = json.dumps({"insight": "This is exactly the kind of monitoring gap Bassir is built to close.",
                          "question_answered": "Could this become a Bassir feature?"})
WRITER_JSON = json.dumps({"hook": "A $40M bet that AI belongs on the jobsite.",
                          "body": "Full linkedin post body about the funding round and what it means.",
                          "media_brief": None})


def test_generate_draft_persists_a_pending_review_post(db_session, persona):
    _seed(db_session, persona)
    cluster_id = _make_cluster(db_session, persona)

    post = generate_draft_for_cluster(
        db_session, cluster_id, "linkedin_post",
        verify_call_fn=_fake(VERIFY_JSON), angle_call_fn=_fake(ANGLE_JSON),
        insight_call_fn=_fake(INSIGHT_JSON), writer_call_fn=_fake(WRITER_JSON),
    )

    assert post.status == "pending_review"
    assert post.hook == "A $40M bet that AI belongs on the jobsite."
    assert post.platform == "linkedin_post"
    assert post.approval_level in ("green", "yellow", "red")
    assert post.fact_confidence is not None


def test_generate_draft_flags_similar_content_as_repeat(db_session, persona):
    _seed(db_session, persona)
    cluster_id_1 = _make_cluster(db_session, persona, title="Saudi PIF backs AI construction monitoring startup A")
    cluster_id_2 = _make_cluster(db_session, persona, title="Saudi PIF backs AI construction monitoring startup B")

    first = generate_draft_for_cluster(
        db_session, cluster_id_1, "linkedin_post",
        verify_call_fn=_fake(VERIFY_JSON), angle_call_fn=_fake(ANGLE_JSON),
        insight_call_fn=_fake(INSIGHT_JSON), writer_call_fn=_fake(WRITER_JSON),
    )
    # second call returns the exact same body -> memory agent must catch it
    second = generate_draft_for_cluster(
        db_session, cluster_id_2, "linkedin_post",
        verify_call_fn=_fake(VERIFY_JSON), angle_call_fn=_fake(ANGLE_JSON),
        insight_call_fn=_fake(INSIGHT_JSON), writer_call_fn=_fake(WRITER_JSON),
    )

    assert first.body == second.body
    assert "previous post" in (second.review_notes or "")
    assert second.approval_level != "green"


def test_regenerate_supersedes_old_draft_and_creates_a_new_one(db_session, persona):
    _seed(db_session, persona)
    cluster_id = _make_cluster(db_session, persona)

    original = generate_draft_for_cluster(
        db_session, cluster_id, "linkedin_post",
        verify_call_fn=_fake(VERIFY_JSON), angle_call_fn=_fake(ANGLE_JSON),
        insight_call_fn=_fake(INSIGHT_JSON), writer_call_fn=_fake(WRITER_JSON),
    )

    new_writer_json = json.dumps({"hook": "A different, regenerated hook.",
                                  "body": "A regenerated body, sufficiently different from the first.",
                                  "media_brief": None})
    regenerated = regenerate_draft(
        db_session, original.id, mode="hook",
        verify_call_fn=_fake(VERIFY_JSON), angle_call_fn=_fake(ANGLE_JSON),
        insight_call_fn=_fake(INSIGHT_JSON), writer_call_fn=_fake(new_writer_json),
    )

    refreshed_original = PostRepository(db_session).get(original.id)
    assert refreshed_original.status == "rejected"   # superseded, audit trail kept
    assert regenerated.id != original.id
    assert regenerated.hook == "A different, regenerated hook."
    assert regenerated.status == "pending_review"


def test_generate_draft_raises_clear_error_for_unknown_cluster(db_session, persona):
    import uuid
    _seed(db_session, persona)
    import pytest
    with pytest.raises(ValueError, match="unknown cluster"):
        generate_draft_for_cluster(db_session, uuid.uuid4(), "linkedin_post")
