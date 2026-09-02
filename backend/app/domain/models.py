"""Domain models for the discovery/scoring/clustering pipeline.

``Article`` mirrors the ``raw_articles`` table (architecture-assessment.md § D) and
replaces ``automation/persona.py``'s ``Story`` dataclass with a validated pydantic
model — same fields, same semantics, now with type checking at construction time.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .text import normalize


class Article(BaseModel):
    title: str
    summary: str = ""
    url: str = ""
    source: str = ""
    source_type: str = "unknown_website"   # key into persona.source_credibility
    published: datetime | None = None
    language: str = "en"
    scores: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)

    model_config = {"frozen": False}

    @property
    def text(self) -> str:
        return normalize(f"{self.title} {self.summary}")


class ClusterResult(BaseModel):
    primary: Article
    supporting: list[Article] = Field(default_factory=list)
    best_source: Article
    source_count: int
    fact_confidence: float

    @property
    def members(self) -> list[Article]:
        return [self.primary] + self.supporting


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
