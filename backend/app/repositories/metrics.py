"""Repository for `performance_metrics` — the raw engagement data behind
the Performance & Learning screen and the learning engine."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PerformanceMetric, Post


class MetricsRepository:
    def __init__(self, session: Session):
        self.session = session

    def record(self, post_id: uuid.UUID, **fields) -> PerformanceMetric:
        row = PerformanceMetric(post_id=post_id, **fields)
        if fields.get("impressions") and fields.get("likes") is not None:
            weighted = (float(fields.get("likes") or 0) + 2 * float(fields.get("comments") or 0)
                       + 3 * float(fields.get("shares") or 0) + 2 * float(fields.get("saves") or 0)
                       + 1.5 * float(fields.get("profile_visits") or 0)
                       + 4 * float(fields.get("followers_gained") or 0))
            row.engagement_rate = weighted / float(fields["impressions"])
        self.session.add(row)
        return row

    def rows_with_pillar(self) -> list[dict]:
        """Every metrics row joined with its post's pillar/platform — the shape
        `domain.learning` expects."""
        stmt = (select(PerformanceMetric, Post.pillar, Post.platform, Post.language)
               .join(Post, Post.id == PerformanceMetric.post_id))
        out = []
        for metric, pillar, platform, language in self.session.execute(stmt):
            out.append({
                "pillar": pillar, "platform": platform, "language": language,
                "impressions": metric.impressions, "views": metric.views, "likes": metric.likes,
                "comments": metric.comments, "shares": metric.shares, "saves": metric.saves,
                "profile_visits": metric.profile_visits, "followers_gained": metric.followers_gained,
                "time": metric.captured_at.strftime("%H:%M") if metric.captured_at else None,
            })
        return out

    def total_impressions(self) -> int:
        rows = self.session.scalars(select(PerformanceMetric.impressions))
        return sum(r for r in rows if r)
