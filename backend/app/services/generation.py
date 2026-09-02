"""Generation service — TRD § 38 steps 7-10: angle -> insight -> platform copy
-> safety check. Orchestrates the four LLM agents plus the deterministic
Safety and Memory checks, and persists the result as a `posts` row with
status='pending_review' (brief rule 5: nothing auto-publishes).

Each LLM agent call accepts an injectable `call_fn` purely so tests can
exercise the full pipeline without hitting the network — production callers
omit it and get the real Anthropic API via app.agents.llm._default_call.
"""

from __future__ import annotations

import uuid
from typing import Callable

from sqlalchemy.orm import Session

from app.agents.angle import run_angle_agent
from app.agents.insight import run_insight_agent
from app.agents.verify import run_verify_agent
from app.agents.writer import run_writer_agent
from app.db.models import Post, RawArticle
from app.domain.clustering import is_repeat
from app.domain.models import Article
from app.domain.safety import classify_approval
from app.repositories.clusters import StoryClusterRepository
from app.repositories.persona import PersonaRepository
from app.repositories.posts import PostRepository


def _article_from_row(row: RawArticle) -> Article:
    """Reconstructs the pure domain Article the agents/clustering logic expect
    from a persisted RawArticle row."""
    return Article(title=row.title, summary=row.summary or "", url=row.url,
                   source=str(row.source_id or ""), language=row.language,
                   published=row.published_at, scores=row.scores or {},
                   meta={"pillar": row.pillar, "region": row.region})


def generate_draft_for_cluster(session: Session, cluster_id: uuid.UUID, platform: str, *,
                                language: str | None = None,
                                verify_call_fn: Callable | None = None,
                                angle_call_fn: Callable | None = None,
                                insight_call_fn: Callable | None = None,
                                writer_call_fn: Callable | None = None) -> Post:
    persona_repo = PersonaRepository(session)
    persona_config = persona_repo.get_active_persona_config()
    if persona_config is None:
        raise RuntimeError("no persona_config in database — run scripts/seed.py first")
    persona = persona_config.config
    language = language or persona["voice"].get("default_language", "en")

    cluster_repo = StoryClusterRepository(session)
    cluster_row = cluster_repo.get(cluster_id)
    if cluster_row is None:
        raise ValueError(f"unknown cluster: {cluster_id}")
    article_rows = cluster_repo.articles_of(cluster_id)
    if not article_rows:
        raise ValueError(f"cluster {cluster_id} has no member articles")

    from app.domain.models import ClusterResult
    articles = [_article_from_row(r) for r in article_rows]
    primary_row = next((r for r in article_rows if r.id == cluster_row.primary_article_id),
                       article_rows[0])
    primary = _article_from_row(primary_row)
    supporting = [a for a in articles if a.url != primary.url]
    cluster_result = ClusterResult(primary=primary, supporting=supporting, best_source=primary,
                                   source_count=cluster_row.source_count,
                                   fact_confidence=float(cluster_row.fact_confidence or 0.0))

    knowledge_snippets = [f"{k.title}: {k.body}" for k in persona_repo.list_public_knowledge()]
    pillar = primary_row.pillar or "ai_technology"

    verify_out = run_verify_agent(cluster_result, persona, language=language, call_fn=verify_call_fn)
    angle_out = run_angle_agent(cluster_result, persona, verify_out.agreed_facts, pillar=pillar,
                                language=language, call_fn=angle_call_fn)
    insight_out = run_insight_agent(cluster_result, persona, angle_out.angle, knowledge_snippets,
                                    language=language, call_fn=insight_call_fn)
    writer_out = run_writer_agent(angle_out.angle, angle_out.why_it_matters, insight_out.insight,
                                  platform, persona, knowledge_snippets, language=language,
                                  call_fn=writer_call_fn)

    fact_conf = float(cluster_row.fact_confidence or 0.0)
    level, reasons = classify_approval(writer_out.body, persona, fact_conf)

    post_repo = PostRepository(session)
    if is_repeat(writer_out.body, post_repo.recent_bodies()):
        if level == "green":
            level = "yellow"
        reasons.append("similar to a previous post (content memory) — hook or angle needs to change")

    post = post_repo.create_draft(
        cluster_id=cluster_id, platform=platform, language=language, pillar=pillar,
        content_type="news_insight", hook=writer_out.hook, body=writer_out.body,
        media_brief=writer_out.media_brief, approval_level=level,
        review_notes="; ".join(reasons) or None, fact_confidence=fact_conf,
        relevance=primary_row.relevance,
    )
    return post


def regenerate_draft(session: Session, post_id: uuid.UUID, *, mode: str = "full", **kwargs) -> Post:
    """Supersedes an existing draft with a freshly generated one for the same
    cluster/platform. `mode` is currently informational (full/hook/angle) —
    all modes re-run the full pipeline in this version; narrower regeneration
    (hook-only, angle-only) is a refinement, not a correctness requirement."""
    post_repo = PostRepository(session)
    old = post_repo.get(post_id)
    if old is None:
        raise ValueError(f"unknown post: {post_id}")
    if old.cluster_id is None:
        raise ValueError("cannot regenerate a post with no source cluster")

    new_post = generate_draft_for_cluster(session, old.cluster_id, old.platform,
                                          language=old.language, **kwargs)
    post_repo.supersede(post_id, reason=f"regenerated ({mode})")
    return new_post
