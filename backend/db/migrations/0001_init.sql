-- ═══════════════════════════════════════════════════════════════════════
-- Initial schema — Yahya AI Content Intelligence Platform
-- Mirrors docs/architecture-assessment.md § D, itself adapted from
-- docs/technical-requirements.md § 2 with the brief's table names.
-- Decisions this migration encodes (see architecture-assessment.md § K):
--   - drafts/published_content are ONE table (`posts`) with a status enum,
--     exposed as two views for the API/dashboard layer.
-- ═══════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector

-- ─────────────────────── Persona & knowledge ───────────────────────

CREATE TABLE persona_config (
    id          SERIAL PRIMARY KEY,
    version     TEXT NOT NULL,
    config      JSONB NOT NULL,             -- full profile/persona.yml, seeded on migration
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX persona_config_one_active ON persona_config (active) WHERE active;

CREATE TABLE pillars (
    key             TEXT PRIMARY KEY,          -- ai_technology, construction_engineering, ...
    label_ar        TEXT NOT NULL,
    label_en        TEXT NOT NULL,
    target_share    NUMERIC(4,3) NOT NULL CHECK (target_share >= 0 AND target_share <= 1),
    multiplier      NUMERIC(4,3) NOT NULL DEFAULT 1.0 CHECK (multiplier BETWEEN 0.7 AND 1.4)
);

CREATE TABLE interests (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    tier        SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 3),
    aliases     TEXT[] NOT NULL DEFAULT '{}',
    pillar      TEXT REFERENCES pillars(key) ON DELETE SET NULL,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE knowledge_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind        TEXT NOT NULL CHECK (kind IN
                    ('bio','company','project','education','opinion','quote','goal','product')),
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    is_public   BOOLEAN NOT NULL DEFAULT FALSE,   -- FALSE = never citable in published content
    confidence  NUMERIC(3,2) NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    source      TEXT,
    embedding   VECTOR(1024),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX knowledge_items_public_idx ON knowledge_items (is_public);

-- ─────────────────────── Sources & intelligence ───────────────────────

CREATE TABLE sources (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    url                 TEXT NOT NULL UNIQUE,
    kind                TEXT NOT NULL CHECK (kind IN ('rss','api','scrape','social')),
    source_type         TEXT NOT NULL,          -- key into system_config.source_credibility
    credibility         SMALLINT NOT NULL CHECK (credibility BETWEEN 0 AND 100),
    region              TEXT,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    last_fetched_at     TIMESTAMPTZ,
    failure_count       SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE raw_articles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       INT REFERENCES sources(id) ON DELETE SET NULL,
    url             TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    summary         TEXT,
    body            TEXT,
    language        TEXT NOT NULL DEFAULT 'en',
    published_at    TIMESTAMPTZ,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedding       VECTOR(1024),
    cluster_id      UUID,                        -- FK added after story_clusters exists
    scores          JSONB,                        -- 7 named components + total (§20)
    relevance       NUMERIC(5,1),
    pillar          TEXT REFERENCES pillars(key) ON DELETE SET NULL,
    region          TEXT,
    entities        JSONB,
    status          TEXT NOT NULL DEFAULT 'new' CHECK
                        (status IN ('new','scored','clustered','used','ignored'))
);
CREATE INDEX raw_articles_relevance_idx ON raw_articles (relevance DESC, published_at DESC);
CREATE INDEX raw_articles_embedding_idx ON raw_articles
    USING hnsw (embedding vector_cosine_ops);

CREATE TABLE story_clusters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    headline        TEXT NOT NULL,
    primary_article_id UUID REFERENCES raw_articles(id) ON DELETE SET NULL,
    source_count    SMALLINT NOT NULL DEFAULT 1,
    fact_confidence NUMERIC(3,2) CHECK (fact_confidence BETWEEN 0 AND 1),
    key_facts       JSONB,
    conflicts       JSONB,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE raw_articles
    ADD CONSTRAINT raw_articles_cluster_fk
    FOREIGN KEY (cluster_id) REFERENCES story_clusters(id) ON DELETE SET NULL;

CREATE TABLE trends (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pillar          TEXT REFERENCES pillars(key) ON DELETE SET NULL,
    headline        TEXT NOT NULL,
    article_ids     UUID[] NOT NULL,
    strength        NUMERIC(5,1),
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE content_opportunities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id      UUID NOT NULL REFERENCES story_clusters(id) ON DELETE CASCADE,
    opportunity_type TEXT NOT NULL,      -- bassir_feature|partnership|investment_theme|competitive_intel
    label           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'new' CHECK
                        (status IN ('new','saved','drafted','ignored')),
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────── Content, approval, publishing ───────────────────────

CREATE TABLE ideas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    pillar          TEXT REFERENCES pillars(key) ON DELETE SET NULL,
    angle           TEXT,
    source_article_id UUID REFERENCES raw_articles(id) ON DELETE SET NULL,
    status          TEXT NOT NULL DEFAULT 'new' CHECK
                        (status IN ('new','drafted','published','parked','rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- `drafts` and `published_content` are ONE table with a status lifecycle
-- (architecture-assessment.md § K.3) — never two physically duplicated tables.
CREATE TABLE posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id      UUID REFERENCES story_clusters(id) ON DELETE SET NULL,
    idea_id         UUID REFERENCES ideas(id) ON DELETE SET NULL,
    platform        TEXT NOT NULL CHECK
                        (platform IN ('linkedin_post','x','x_thread','instagram','tiktok','article')),
    language        TEXT NOT NULL CHECK (language IN ('ar','en')),
    pillar          TEXT REFERENCES pillars(key) ON DELETE SET NULL,
    content_type    TEXT NOT NULL,          -- news_insight|educational|... (§27)
    hook            TEXT,
    body            TEXT NOT NULL,
    media_brief     TEXT,
    approval_level  TEXT NOT NULL CHECK (approval_level IN ('green','yellow','red')),
    review_notes    TEXT,
    fact_confidence NUMERIC(3,2) CHECK (fact_confidence BETWEEN 0 AND 1),
    relevance       NUMERIC(5,1),
    similarity_max  NUMERIC(4,3),
    status          TEXT NOT NULL DEFAULT 'draft' CHECK
                        (status IN ('draft','pending_review','approved','rejected',
                                    'scheduled','posted','failed')),
    scheduled_for   TIMESTAMPTZ,
    posted_at       TIMESTAMPTZ,
    external_id     TEXT,                   -- id returned by the platform on publish
    embedding       VECTOR(1024),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX posts_status_schedule_idx ON posts (status, scheduled_for);
CREATE INDEX posts_embedding_idx ON posts USING hnsw (embedding vector_cosine_ops);

-- Logical views for the API/dashboard layer — see § K.3.
CREATE VIEW drafts AS
    SELECT * FROM posts WHERE status IN ('draft', 'pending_review');
CREATE VIEW published_content AS
    SELECT * FROM posts WHERE status = 'posted';

CREATE TABLE approval_decisions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id     UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    decision    TEXT NOT NULL CHECK (decision IN ('approved','rejected','edited')),
    edit_diff   TEXT,
    reason_tags TEXT[] NOT NULL DEFAULT '{}',   -- tone|inaccurate|off-brand|repetitive|sensitive|weak-insight
    decided_by  TEXT NOT NULL DEFAULT 'yahya',
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX approval_decisions_reason_tags_idx ON approval_decisions USING gin (reason_tags);

CREATE TABLE performance_metrics (
    id                  BIGSERIAL PRIMARY KEY,
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    impressions         INT, views INT, likes INT, comments INT, shares INT, saves INT,
    profile_visits      INT, followers_gained INT, clicks INT,
    engagement_rate     NUMERIC(7,4)
);

CREATE TABLE learning_weights (
    id              BIGSERIAL PRIMARY KEY,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    weights         JSONB NOT NULL,          -- {pillar: multiplier}
    sample_size     INT,
    notes           TEXT
);

CREATE TABLE pillar_distribution (
    id              BIGSERIAL PRIMARY KEY,
    pillar          TEXT NOT NULL REFERENCES pillars(key) ON DELETE CASCADE,
    window_start    DATE NOT NULL,
    window_end      DATE NOT NULL,
    target_share    NUMERIC(4,3) NOT NULL,
    actual_share    NUMERIC(4,3) NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE system_config (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  TEXT
);

CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    entity      TEXT NOT NULL,
    entity_id   UUID,
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────── Seed: safety defaults ───────────────────────
-- auto_publish_green MUST default to false — brief rule 5 is non-negotiable
-- for the first 3 months. A CI check (backend/tests/test_seed_safety.py)
-- fails the build if this default is ever seeded as true.
INSERT INTO system_config (key, value, updated_by) VALUES
    ('auto_publish_green', 'false'::jsonb, 'migration'),
    ('require_approval',   'true'::jsonb,  'migration'),
    ('timezone',           '"Asia/Riyadh"'::jsonb, 'migration');
