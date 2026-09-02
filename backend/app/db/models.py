"""SQLAlchemy ORM models — mirror ``backend/db/migrations/0001_init.sql`` exactly.

The SQL migration file is the canonical schema definition (it's what actually
runs against Postgres, and it's what ``tests/test_seed_safety.py`` checks). These
models describe the same tables for the repository/query layer. Keep the two in
sync by hand for now; Phase 1's remaining work item is switching to
Alembic-managed migrations generated from these models once the schema
stabilizes past this first cut.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (ARRAY, TIMESTAMP, ForeignKey, Numeric, SmallInteger,
                        String, Text, func)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Pillar(Base):
    __tablename__ = "pillars"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    label_ar: Mapped[str] = mapped_column(Text, nullable=False)
    label_en: Mapped[str] = mapped_column(Text, nullable=False)
    target_share: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    multiplier: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=1.0)


class Interest(Base):
    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    pillar: Mapped[str | None] = mapped_column(ForeignKey("pillars.key", ondelete="SET NULL"))
    enabled: Mapped[bool] = mapped_column(default=True)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(default=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)
    source: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class PersonaConfig(Base):
    __tablename__ = "persona_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    credibility: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    region: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    failure_count: Mapped[int] = mapped_column(SmallInteger, default=0)


class RawArticle(Base):
    __tablename__ = "raw_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, default="en")
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_clusters.id", ondelete="SET NULL"))
    scores: Mapped[dict | None] = mapped_column(JSONB)
    relevance: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pillar: Mapped[str | None] = mapped_column(ForeignKey("pillars.key", ondelete="SET NULL"))
    region: Mapped[str | None] = mapped_column(Text)
    entities: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="new")


class StoryCluster(Base):
    __tablename__ = "story_clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    primary_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_articles.id", ondelete="SET NULL"))
    source_count: Mapped[int] = mapped_column(SmallInteger, default=1)
    fact_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    key_facts: Mapped[dict | None] = mapped_column(JSONB)
    conflicts: Mapped[dict | None] = mapped_column(JSONB)
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Trend(Base):
    __tablename__ = "trends"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    pillar: Mapped[str | None] = mapped_column(ForeignKey("pillars.key", ondelete="SET NULL"))
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    article_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    strength: Mapped[float | None] = mapped_column(Numeric(5, 1))
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class ContentOpportunity(Base):
    __tablename__ = "content_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_clusters.id", ondelete="CASCADE"), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="new")
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    title: Mapped[str] = mapped_column(Text, nullable=False)
    pillar: Mapped[str | None] = mapped_column(ForeignKey("pillars.key", ondelete="SET NULL"))
    angle: Mapped[str | None] = mapped_column(Text)
    source_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_articles.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text, default="new")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_clusters.id", ondelete="SET NULL"))
    idea_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ideas.id", ondelete="SET NULL"))
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    pillar: Mapped[str | None] = mapped_column(ForeignKey("pillars.key", ondelete="SET NULL"))
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    hook: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    media_brief: Mapped[str | None] = mapped_column(Text)
    approval_level: Mapped[str] = mapped_column(Text, nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text)
    fact_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    relevance: Mapped[float | None] = mapped_column(Numeric(5, 1))
    similarity_max: Mapped[float | None] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(Text, default="draft")
    scheduled_for: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    external_id: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    approvals: Mapped[list["ApprovalDecision"]] = relationship(back_populates="post")


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    edit_diff: Mapped[str | None] = mapped_column(Text)
    reason_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    decided_by: Mapped[str] = mapped_column(Text, default="yahya")
    decided_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="approvals")


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    impressions: Mapped[int | None]
    views: Mapped[int | None]
    likes: Mapped[int | None]
    comments: Mapped[int | None]
    shares: Mapped[int | None]
    saves: Mapped[int | None]
    profile_visits: Mapped[int | None]
    followers_gained: Mapped[int | None]
    clicks: Mapped[int | None]
    engagement_rate: Mapped[float | None] = mapped_column(Numeric(7, 4))


class LearningWeight(Base):
    __tablename__ = "learning_weights"

    id: Mapped[int] = mapped_column(primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sample_size: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)


class PillarDistribution(Base):
    __tablename__ = "pillar_distribution"

    id: Mapped[int] = mapped_column(primary_key=True)
    pillar: Mapped[str] = mapped_column(ForeignKey("pillars.key", ondelete="CASCADE"), nullable=False)
    window_start: Mapped[datetime] = mapped_column(nullable=False)
    window_end: Mapped[datetime] = mapped_column(nullable=False)
    target_share: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    actual_share: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class User(Base):
    """Dashboard login accounts — see db/migrations/0002_users.sql."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
