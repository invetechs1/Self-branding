"""Repository for `content_opportunities` and `trends`."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ContentOpportunity, Trend


class OpportunityRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, cluster_id: uuid.UUID, opportunity_type: str, label: str) -> ContentOpportunity:
        row = ContentOpportunity(cluster_id=cluster_id, opportunity_type=opportunity_type, label=label)
        self.session.add(row)
        return row

    def list_new(self, limit: int = 50) -> list[ContentOpportunity]:
        stmt = (select(ContentOpportunity).where(ContentOpportunity.status == "new")
               .order_by(ContentOpportunity.detected_at.desc()).limit(limit))
        return list(self.session.scalars(stmt))

    def set_status(self, opportunity_id: uuid.UUID, status: str) -> None:
        row = self.session.get(ContentOpportunity, opportunity_id)
        if row is None:
            raise ValueError(f"unknown opportunity: {opportunity_id}")
        row.status = status


class TrendRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, *, pillar: str, headline: str, article_ids: list[uuid.UUID],
              strength: float) -> Trend:
        row = Trend(pillar=pillar, headline=headline, article_ids=article_ids, strength=strength)
        self.session.add(row)
        return row

    def recent(self, limit: int = 10) -> list[Trend]:
        stmt = select(Trend).order_by(Trend.detected_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))
