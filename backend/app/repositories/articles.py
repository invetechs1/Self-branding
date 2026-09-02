"""Repository for `raw_articles` — the discovery pipeline's landing table.

Mirrors what ``automation/news_engine.py`` did with ``queue/news.jsonl``: only
articles that cross the relevance threshold get persisted (TRD § 20 — the store
stays a curated pipeline, not a firehose dump of every RSS item).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.models import Article
from app.db.models import RawArticle


class RawArticleRepository:
    def __init__(self, session: Session):
        self.session = session

    def existing_urls(self, urls: list[str]) -> set[str]:
        if not urls:
            return set()
        rows = self.session.scalars(select(RawArticle.url).where(RawArticle.url.in_(urls)))
        return set(rows)

    def save_scored(self, article: Article, *, source_id: int | None) -> RawArticle:
        """Persists an already-scored Article (from domain.scoring.score_article)."""
        row = RawArticle(
            source_id=source_id, url=article.url, title=article.title, summary=article.summary,
            language=article.language, published_at=article.published,
            scores=article.scores, relevance=article.scores.get("total"),
            pillar=article.meta.get("pillar"), region=article.meta.get("region"),
            entities={"domains": article.meta.get("domains", []),
                     "interest_hits": article.meta.get("interest_hits", [])},
            status="scored",
        )
        self.session.add(row)
        self.session.flush()   # assign row.id without committing
        return row

    def list_unclustered(self, min_relevance: float = 0.0) -> list[RawArticle]:
        stmt = (select(RawArticle)
               .where(RawArticle.status == "scored", RawArticle.cluster_id.is_(None),
                      RawArticle.relevance >= min_relevance)
               .order_by(RawArticle.relevance.desc()))
        return list(self.session.scalars(stmt))

    def assign_cluster(self, article_id: uuid.UUID, cluster_id: uuid.UUID) -> None:
        """Marks an article as belonging to a cluster (primary or supporting alike).
        `status` moves to 'used' only later, when a post is actually generated from
        its cluster (Phase 2) — 'clustered' just means dedup has processed it."""
        row = self.session.get(RawArticle, article_id)
        if row is None:
            raise ValueError(f"unknown article: {article_id}")
        row.cluster_id = cluster_id
        row.status = "clustered"

    def top(self, limit: int = 10) -> list[RawArticle]:
        stmt = select(RawArticle).order_by(RawArticle.relevance.desc()).limit(limit)
        return list(self.session.scalars(stmt))
