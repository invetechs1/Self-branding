"""Repository for the `sources` table — seeded from automation/sources.yml."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Source


class SourceRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, *, name: str, url: str, kind: str, source_type: str,
              credibility: int, region: str | None) -> None:
        stmt = pg_insert(Source).values(name=name, url=url, kind=kind, source_type=source_type,
                                        credibility=credibility, region=region)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Source.url],
            set_={"name": name, "kind": kind, "source_type": source_type,
                 "credibility": credibility, "region": region})
        self.session.execute(stmt)

    def list_enabled(self) -> list[Source]:
        return list(self.session.scalars(select(Source).where(Source.enabled.is_(True))))

    def list_all(self) -> list[Source]:
        return list(self.session.scalars(select(Source).order_by(Source.name)))

    def set_enabled(self, source_id: int, enabled: bool) -> Source:
        source = self.session.get(Source, source_id)
        if source is None:
            raise ValueError(f"unknown source: {source_id}")
        source.enabled = enabled
        if enabled:
            source.failure_count = 0   # re-enabling clears the auto-disable strike count
        return source

    def record_failure(self, source_id: int) -> None:
        source = self.session.get(Source, source_id)
        if source:
            source.failure_count += 1
            if source.failure_count >= 5:
                source.enabled = False   # TRD § 5: auto-disable after 5 consecutive failures

    def record_success(self, source_id: int, fetched_at) -> None:
        source = self.session.get(Source, source_id)
        if source:
            source.failure_count = 0
            source.last_fetched_at = fetched_at
