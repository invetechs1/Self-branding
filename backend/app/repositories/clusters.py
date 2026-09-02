"""Repository for `story_clusters` — persists ClusterResult (domain.clustering)
and links member raw_articles to it. Enforces brief § 15 at the storage layer:
one row per real-world event, never one row per source report of that event.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import ClusterResult
from app.db.models import RawArticle, StoryCluster
from app.repositories.articles import RawArticleRepository


class StoryClusterRepository:
    def __init__(self, session: Session):
        self.session = session
        self.articles = RawArticleRepository(session)

    def create_from_cluster_result(self, cluster: ClusterResult,
                                   article_ids_by_url: dict[str, object]) -> StoryCluster:
        """`article_ids_by_url` maps article.url -> RawArticle.id for every member,
        since domain.ClusterResult carries pydantic Article objects (no DB id)."""
        primary_id = article_ids_by_url[cluster.primary.url]
        row = StoryCluster(
            headline=cluster.primary.title,
            primary_article_id=primary_id,
            source_count=cluster.source_count,
            fact_confidence=cluster.fact_confidence,
            key_facts={"sources": [{"name": m.source, "url": m.url, "title": m.title}
                                   for m in cluster.members]},
            conflicts=None,
        )
        self.session.add(row)
        self.session.flush()

        for member in cluster.members:
            self.articles.assign_cluster(article_ids_by_url[member.url], row.id)

        return row

    def get(self, cluster_id) -> StoryCluster | None:
        return self.session.get(StoryCluster, cluster_id)

    def recent(self, limit: int = 20) -> list[StoryCluster]:
        stmt = select(StoryCluster).order_by(StoryCluster.first_seen_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def articles_of(self, cluster_id) -> list[RawArticle]:
        stmt = select(RawArticle).where(RawArticle.cluster_id == cluster_id)
        return list(self.session.scalars(stmt))
