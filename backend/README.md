# Backend — Yahya AI Content Intelligence Platform

FastAPI + PostgreSQL/pgvector implementation of the platform described in
[`docs/architecture-assessment.md`](../docs/architecture-assessment.md) and
[`docs/technical-requirements.md`](../docs/technical-requirements.md). Ports the working logic from
`automation/` (scoring, clustering, safety, learning) into a typed, tested, database-backed service —
see the architecture assessment's reuse map for what came from where.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # or: source .venv/bin/activate on Linux/Mac
pip install -r requirements-dev.txt

cp .env.example .env          # fill in DATABASE_URL, API_KEY, ANTHROPIC_API_KEY at minimum
```

You need a running Postgres with the `pgvector` extension available (the `pgvector/pgvector:pg16` Docker
image has it built in).

## Database

```bash
# apply the schema, in order (no migration tool wired up yet — see architecture-assessment.md § D)
psql "$DATABASE_URL" -f db/migrations/0001_init.sql
psql "$DATABASE_URL" -f db/migrations/0002_users.sql

# load profile/persona.yml, profile/facts.yml, automation/sources.yml into it
python scripts/seed.py

# create a dashboard login account (idempotent — re-run to change a password)
python scripts/create_user.py --email you@example.com --password 'a-real-password'
```

Re-run `scripts/seed.py` any time those source files change — it's idempotent.

## Running

```bash
# discovery cycle (fetch RSS -> score -> cluster -> persist) — the DB-backed
# equivalent of automation/news_engine.py --discover
python scripts/discover.py

# API server
uvicorn app.api.main:app --reload
```

## Tests

```bash
pytest tests/ -v
```

Integration tests spin up a disposable `pgvector/pgvector:pg16` Docker container automatically (see
`tests/conftest.py`) and tear it down afterward — no manual database setup needed to run the suite.
Agent tests never call the real Anthropic API; every LLM call is injectable and faked in tests.

## Layout

| Path | Role |
|---|---|
| `app/domain/` | Pure logic — scoring, clustering, safety, opportunities/trends (ported from `automation/persona.py`) |
| `app/agents/` | The 4 LLM-backed agents (Verify, Angle, Insight, Writer) — strict JSON contracts, retry-then-raise |
| `app/services/` | Orchestration — discovery pipeline, content generation pipeline |
| `app/repositories/` | One class per DB aggregate — the only layer that touches SQLAlchemy sessions directly |
| `app/api/` | FastAPI routers — thin, no business logic |
| `db/migrations/` | Schema (hand-written SQL for now; see architecture-assessment.md § D for the Alembic migration plan) |
| `scripts/` | CLI entrypoints: `seed.py`, `discover.py`, `create_user.py` |
