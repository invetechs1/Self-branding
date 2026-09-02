"""Read-only endpoints backing the "Today's Intelligence" and "Content
Opportunities" dashboard screens (architecture-assessment.md § F). Discovery
itself is NOT triggered over HTTP — it's a scheduled/background job (brief's
async-processing rule: ingestion must not block web requests), run via
scripts/discover.py today and a Celery beat task once the worker stack lands
(Phase 1/8)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.api.schemas import SourceOut, source_lookup
from app.db.base import get_session
from app.db.models import RawArticle
from app.repositories.articles import RawArticleRepository
from app.repositories.clusters import StoryClusterRepository
from app.repositories.opportunities import OpportunityRepository

router = APIRouter(tags=["intelligence"], dependencies=[Depends(require_api_key)])


class ArticleOut(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    source: SourceOut | None = None
    relevance: float | None = None
    pillar: str | None = None
    region: str | None = None
    scores: dict | None = None


class ClusterOut(BaseModel):
    id: uuid.UUID
    headline: str
    source_count: int
    fact_confidence: float | None = None
    relevance: float | None = None
    pillar: str | None = None
    region: str | None = None
    freshness: str | None = None


class OpportunityOut(BaseModel):
    id: uuid.UUID
    cluster_id: uuid.UUID
    opportunity_type: str
    label: str
    status: str
    headline: str
    pillar: str | None = None
    region: str | None = None
    relevance: float | None = None
    fact_confidence: float | None = None
    source_count: int


class ClusterDetailOut(ClusterOut):
    articles: list[ArticleOut]
    opportunities: list[OpportunityOut]


def _article_out(row: RawArticle, lookup: dict[int, SourceOut]) -> ArticleOut:
    return ArticleOut(id=row.id, title=row.title, url=row.url, relevance=row.relevance,
                      pillar=row.pillar, region=row.region, scores=row.scores,
                      source=lookup.get(row.source_id))


def _freshness(published_at: datetime | None) -> str | None:
    if published_at is None:
        return None
    delta = datetime.now(timezone.utc) - published_at
    hours = int(delta.total_seconds() // 3600)
    return f"{hours}h ago" if hours < 48 else f"{hours // 24}d ago"


def _cluster_out(session: Session, cluster, primary: RawArticle | None) -> ClusterOut:
    return ClusterOut(id=cluster.id, headline=cluster.headline, source_count=cluster.source_count,
                      fact_confidence=cluster.fact_confidence,
                      relevance=primary.relevance if primary else None,
                      pillar=primary.pillar if primary else None,
                      region=primary.region if primary else None,
                      freshness=_freshness(primary.published_at) if primary else None)


@router.get("/clusters", response_model=list[ClusterOut])
def list_clusters(limit: int = 20, session: Session = Depends(get_session)) -> list[ClusterOut]:
    repo = StoryClusterRepository(session)
    out = []
    for cluster in repo.recent(limit):
        primary = (session.get(RawArticle, cluster.primary_article_id)
                  if cluster.primary_article_id else None)
        out.append(_cluster_out(session, cluster, primary))
    return out


@router.get("/clusters/{cluster_id}", response_model=ClusterDetailOut)
def get_cluster(cluster_id: uuid.UUID, session: Session = Depends(get_session)) -> ClusterDetailOut:
    repo = StoryClusterRepository(session)
    cluster = repo.get(cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    articles = repo.articles_of(cluster_id)
    lookup = source_lookup(session, articles)
    primary = next((a for a in articles if a.id == cluster.primary_article_id), None)

    opp_repo = OpportunityRepository(session)
    opps = [o for o in opp_repo.list_new(limit=200) if o.cluster_id == cluster_id]

    base = _cluster_out(session, cluster, primary)
    return ClusterDetailOut(
        **base.model_dump(),
        articles=[_article_out(a, lookup) for a in articles],
        opportunities=[OpportunityOut(
            id=o.id, cluster_id=cluster_id, opportunity_type=o.opportunity_type, label=o.label,
            status=o.status, headline=cluster.headline, pillar=base.pillar, region=base.region,
            relevance=base.relevance, fact_confidence=base.fact_confidence,
            source_count=cluster.source_count) for o in opps],
    )


@router.get("/articles/top", response_model=list[ArticleOut])
def top_articles(limit: int = 10, session: Session = Depends(get_session)) -> list[ArticleOut]:
    rows = RawArticleRepository(session).top(limit)
    lookup = source_lookup(session, rows)
    return [_article_out(a, lookup) for a in rows]


@router.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(limit: int = 50, session: Session = Depends(get_session)) -> list[OpportunityOut]:
    opp_repo = OpportunityRepository(session)
    cluster_repo = StoryClusterRepository(session)
    out = []
    for o in opp_repo.list_new(limit):
        cluster = cluster_repo.get(o.cluster_id)
        if cluster is None:
            continue
        articles = cluster_repo.articles_of(cluster.id)
        primary = next((a for a in articles if a.id == cluster.primary_article_id), None)
        base = _cluster_out(session, cluster, primary)
        out.append(OpportunityOut(id=o.id, cluster_id=o.cluster_id, opportunity_type=o.opportunity_type,
                                  label=o.label, status=o.status, headline=cluster.headline,
                                  pillar=base.pillar, region=base.region, relevance=base.relevance,
                                  fact_confidence=base.fact_confidence, source_count=cluster.source_count))
    return sorted(out, key=lambda o: -(o.relevance or 0))


@router.post("/opportunities/{opportunity_id}/dismiss", response_model=dict)
def dismiss_opportunity(opportunity_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    try:
        OpportunityRepository(session).set_status(opportunity_id, "ignored")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    session.commit()
    return {"id": str(opportunity_id), "status": "ignored"}
