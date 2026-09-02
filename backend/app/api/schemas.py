"""Shared response-model pieces used by more than one router."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import RawArticle, Source


class SourceOut(BaseModel):
    name: str
    credibility: int


def source_lookup(session: Session, article_rows: list[RawArticle]) -> dict[int, SourceOut]:
    ids = {a.source_id for a in article_rows if a.source_id is not None}
    if not ids:
        return {}
    sources = session.query(Source).filter(Source.id.in_(ids)).all()
    return {s.id: SourceOut(name=s.name, credibility=s.credibility) for s in sources}
