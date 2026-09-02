"""Performance & Learning endpoints (brief § 11 / architecture-assessment.md
§ F "avoid black-box analytics — explain WHY the system is learning
something"). All numbers are computed from real tables — a fresh install with
no published posts correctly shows zeros/empty lists, not fabricated data.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.db.base import get_session
from app.domain.learning import engagement_rate
from app.repositories.learning import LearningRepository
from app.repositories.metrics import MetricsRepository
from app.repositories.persona import PersonaRepository
from app.services.learning import recompute_learning_weights

router = APIRouter(prefix="/performance", tags=["performance"], dependencies=[Depends(require_api_key)])


class PlatformPerformance(BaseModel):
    platform: str
    avg_engagement_rate: float
    post_count: int


class PillarMix(BaseModel):
    key: str
    label: str
    target_share: float
    actual_share: float
    multiplier: float


class LearnedInsight(BaseModel):
    pillar: str
    label: str
    text: str


class PerformanceSummaryOut(BaseModel):
    posts_published: int
    approved: int
    rejected: int
    approval_rate: float | None
    total_impressions: int
    avg_engagement_rate: float
    platform_performance: list[PlatformPerformance]
    pillar_mix: list[PillarMix]
    learned: list[LearnedInsight]
    sample_size: int


class PublishedPostOut(BaseModel):
    id: uuid.UUID
    platform: str
    pillar: str | None
    hook: str | None
    posted_at: datetime | None
    impressions: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    engagement_rate: float | None


@router.get("/summary", response_model=PerformanceSummaryOut)
def get_summary(session: Session = Depends(get_session)) -> PerformanceSummaryOut:
    persona_repo = PersonaRepository(session)
    metrics_repo = MetricsRepository(session)
    learning_repo = LearningRepository(session)

    pillars = persona_repo.list_pillars()
    metric_rows = metrics_repo.rows_with_pillar()
    approved, rejected = learning_repo.approval_counts()
    decided = approved + rejected

    # count posted posts directly via a lightweight query instead of list_drafts (which
    # only returns draft/pending_review) — see PostRepository for the status lifecycle
    from sqlalchemy import select, func
    from app.db.models import Post
    posts_published = session.scalar(select(func.count()).select_from(Post)
                                      .where(Post.status == "posted")) or 0

    total_impressions = metrics_repo.total_impressions()
    avg_er = (sum(engagement_rate(r) for r in metric_rows) / len(metric_rows)) if metric_rows else 0.0

    by_platform: dict[str, list[float]] = {}
    for row in metric_rows:
        by_platform.setdefault(row["platform"], []).append(engagement_rate(row))
    platform_performance = [
        PlatformPerformance(platform=p, avg_engagement_rate=round(sum(v) / len(v), 4), post_count=len(v))
        for p, v in by_platform.items()
    ]

    total_posted = max(1, posts_published)
    by_pillar_count: dict[str, int] = {}
    for row in session.execute(select(Post.pillar).where(Post.status == "posted")):
        if row[0]:
            by_pillar_count[row[0]] = by_pillar_count.get(row[0], 0) + 1

    latest = learning_repo.latest()
    detail = (latest.weights or {}).get("detail", {}) if latest else {}

    pillar_mix = [PillarMix(key=p.key, label=p.label_en, target_share=float(p.target_share),
                            actual_share=round(by_pillar_count.get(p.key, 0) / total_posted, 3),
                            multiplier=float(p.multiplier)) for p in pillars]

    learned = [LearnedInsight(pillar=p.key, label=p.label_en, text=detail[p.key]["why"])
              for p in pillars if p.key in detail and detail[p.key].get("why")
              and "not enough data" not in detail[p.key]["why"]]

    return PerformanceSummaryOut(
        posts_published=posts_published, approved=approved, rejected=rejected,
        approval_rate=round(approved / decided, 3) if decided else None,
        total_impressions=total_impressions, avg_engagement_rate=round(avg_er, 4),
        platform_performance=platform_performance, pillar_mix=pillar_mix, learned=learned,
        sample_size=(latest.sample_size if latest else 0),
    )


@router.get("/posts", response_model=list[PublishedPostOut])
def list_published_posts(session: Session = Depends(get_session)) -> list[PublishedPostOut]:
    from sqlalchemy import select
    from app.db.models import Post, PerformanceMetric

    stmt = (select(Post, PerformanceMetric)
           .outerjoin(PerformanceMetric, PerformanceMetric.post_id == Post.id)
           .where(Post.status == "posted").order_by(Post.posted_at.desc()))
    out = []
    for post, metric in session.execute(stmt):
        out.append(PublishedPostOut(
            id=post.id, platform=post.platform, pillar=post.pillar, hook=post.hook,
            posted_at=post.posted_at,
            impressions=metric.impressions if metric else None,
            likes=metric.likes if metric else None,
            comments=metric.comments if metric else None,
            shares=metric.shares if metric else None,
            engagement_rate=float(metric.engagement_rate) if metric and metric.engagement_rate is not None else None,
        ))
    return out


@router.post("/recompute")
def recompute(session: Session = Depends(get_session)) -> dict:
    result = recompute_learning_weights(session)
    session.commit()
    return result
