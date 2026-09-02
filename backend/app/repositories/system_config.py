"""Repository for `system_config` — the safety-critical toggles (brief rule 5).

Deliberately narrow: ``set_auto_publish_green`` exists as its own explicit,
logged method rather than a generic ``set(key, value)`` writer, so flipping the
platform's single most dangerous setting is never a side effect of a generic
settings-save action.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import SystemConfig


class SystemConfigRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, key: str, default=None):
        row = self.session.get(SystemConfig, key)
        return row.value if row else default

    def set(self, key: str, value, updated_by: str) -> None:
        stmt = pg_insert(SystemConfig).values(key=key, value=value, updated_by=updated_by)
        stmt = stmt.on_conflict_do_update(
            index_elements=[SystemConfig.key],
            set_={"value": value, "updated_by": updated_by, "updated_at": SystemConfig.updated_at})
        self.session.execute(stmt)

    def all(self) -> dict:
        return {row.key: row.value for row in self.session.scalars(select(SystemConfig))}

    def set_auto_publish_green(self, enabled: bool, *, updated_by: str) -> None:
        """The one setting the brief forbids flipping casually — first 3 months, always False."""
        self.set("auto_publish_green", enabled, updated_by)
