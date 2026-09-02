# Architecture Assessment — Yahya Al Salamah AI Content Intelligence Platform

> Written before any implementation, per the brief's explicit instruction. Covers sections A–K
> requested in the brief. Cross-references the two existing specs so nothing here contradicts them:
> [`profile/persona-spec.md`](../profile/persona-spec.md) (human spec, 53 sections) and
> [`docs/technical-requirements.md`](technical-requirements.md) (TRD: DB schema, agent table, scoring,
> approval workflow, scheduler, dashboard, §1–13).

---

## A. Architecture Assessment (current state)

### A1. What this repository actually is today

There is **no web application, no database, no dashboard, and no OAuth integration anywhere in this
repo.** What exists is:

1. A **static personal website** (`site/index.html`) — single-file bilingual (AR/EN) HTML/CSS/JS,
   deployed via Docker/nginx to a shared VPS. Unrelated to the content platform except that it will
   eventually host published articles (`publish.py::post_article` writes to `site/articles/`).
2. A **working CLI reference pipeline** (`automation/*.py`) that already implements most of the
   *business logic* the brief asks for — see C below. It runs today via `python automation/news_engine.py
   --discover` etc., persists state in flat files (JSONL/CSV/YAML), and is scheduled today via two
   GitHub Actions workflows (`.github/workflows/intelligence.yml`, `publish.yml`), not Celery/cron on a
   server.
3. Two **specification documents** that are more complete than typical greenfield projects ever start
   with: `profile/persona-spec.md` (53 numbered sections — the "why") and `docs/technical-requirements.md`
   (Postgres schema, 11-agent table, scoring algorithm, approval workflow, scheduler cadence, platform
   integration notes, dashboard screens, learning formula, security notes, acceptance criteria, 6-phase
   plan). **The brief in this conversation is, almost line for line, a re-statement of these two files.**
4. `profile/facts.yml` — the single source of truth for everything the AI is allowed to claim about
   Yahya. Currently has several `TODO` fields (university/year, exact years of experience, one project
   figure, one failure story) that block the highest-value personal-experience content until filled.

### A2. Answers to the 15 inspection points

| # | Point | Finding |
|---|---|---|
| 1 | Repo structure | `automation/` (CLI engine), `site/` (static site, unrelated), `profile/` (persona+facts), `docs/`, `content/`, `analytics/`, `outreach/`, `strategy/`, `.github/workflows/`. No `backend/`, `frontend/`, `db/`, `tests/`. |
| 2 | Frontend | None, beyond the unrelated static site. No React/Next.js/Vue, no `package.json` anywhere in the repo. |
| 3 | Backend | None. No web server, no API. `automation/*.py` are argparse CLI scripts run locally or in CI. |
| 4 | Database | None. State lives in `automation/queue/news.jsonl`, `automation/queue/queue.csv`, `automation/learning/weights.yml`, `analytics/performance.csv` (manually filled — no metrics API polling exists). |
| 5 | Existing automation / reference implementation | **This is the strongest asset in the repo.** `persona.py` is a pure, dependency-free scoring/clustering/safety engine with an inline self-test (`--self-test`, 10 assertions, all passing logic for relevance scoring, clustering, fact confidence, approval classification). `news_engine.py` (discovery+ranking+weekly report), `generate_posts.py` (Claude-based drafting, two modes: from-news / from-idea-bank), `publish.py` (gated publisher, per-platform functions), `feedback.py` (learning-weight computation with floors/caps, matches TRD §10 exactly). |
| 6 | CLI | Yes — this *is* the product today. Five commands cover discovery, scoring, generation, publishing, learning. |
| 7 | API integrations | X (tweepy, OAuth1.0a), LinkedIn (raw REST, static bearer token, **no refresh logic** despite TRD §8.2 requiring it), Instagram/TikTok (**stubbed as `manual`** — no Graph API calls implemented). No News API/GDELT calls — RSS-only via `feedparser`. |
| 8 | Components / design system | None beyond the static site's own inline CSS (see separate design-system note below). |
| 9 | Routing / auth / state management | N/A — no app exists to route or authenticate against. |
| 10 | Environment configuration | `automation/config.example.yml` → copy to `config.yml` (gitignored). Plaintext, no secrets manager, no encryption at rest. CI publish workflow builds `config.yml` from GitHub Secrets at runtime (reasonable for CI, not sufficient for a persistent server). |
| 11 | Tests | None as files. Only `persona.py`'s inline `_self_test()` (10 logic assertions, no pytest, no fixtures, no CI test job — though `intelligence.yml` does run `--self-test` as a CI step before discovery). |
| 12 | Deployment | Two independent Docker images (`Dockerfile.site`, `Dockerfile.automation`) built/pushed manually to a shared VPS (`13.140.138.252`) hosting ~40 unrelated client projects; `docker-compose.yml` covers local dev only. Scheduling is GitHub Actions cron, not a server-side scheduler. |
| 13 | What can be reused | The entire `automation/persona.py` scoring/clustering/safety/prompt-building logic — it is correct, tested, and matches the TRD formula exactly. `sources.yml` (17 RSS feeds pre-scored by credibility). `generate_posts.py`'s prompt engineering (news_prompt/idea_prompt) is a good first draft of the Writer+Insight+Angle agent combined. `publish.py`'s approval gate (`publishable()`) is the correct deterministic gate the brief demands ("LLMs must not control publishing"). |
| 14 | What needs refactoring | Flat-file state → Postgres. The single combined LLM call in `generate_posts.py` (angle+insight+writer in one prompt) → split into the discrete agents the TRD table already names, each independently testable. LinkedIn token handling → add refresh. Lexical clustering (`similarity()`, Jaccard+overlap) → keep as a cheap first pass, add pgvector cosine similarity as the real dedup mechanism (TRD explicitly recommends this hybrid). |
| 15 | What's missing entirely | Database, backend API, dashboard (all 5 screens), authentication, OAuth flows + token refresh, async job runner, semantic embeddings, metrics auto-collection from platform APIs, encryption/secrets manager, structured logging/observability, a test suite, Instagram/TikTok publishing. |

### A3. Design reference (site's visual language)

The only existing UI is `site/index.html`: light background (`#fafaf7`), dark ink (`#1a1a2e`), a single
accent teal (`#0f6b5c`), system font stack, RTL-first with an EN/AR toggle, generous line-height (1.8),
rounded cards, a dark CTA band. It is minimal and calm — consistent with the brief's UX quality bar
("premium, calm, trustworthy, not overwhelming"). This palette/typography is the right seed for the
dashboard's design tokens (see F), but the site itself has no components worth reusing structurally
(no nav, no tables, no forms, no modals) — the dashboard is a genuine greenfield UI build.

---

## B. Recommended Architecture

Adopt the TRD's proposed stack as-is — it was already chosen correctly and matches the brief's own
"prefer modular monolith, avoid premature microservices" principle:

```
Next.js dashboard (5 screens)  ──────────────┐
                                              │ REST/JSON, session auth
FastAPI backend (modular monolith)  ◄────────┘
 ├─ domain/            (pure logic — ported from automation/persona.py, now typed + unit-testable)
 ├─ agents/             11 modules, strict pydantic I/O contracts (see E)
 ├─ services/           discovery, scoring, clustering, generation, safety, publishing, learning
 ├─ repositories/       Postgres access, one per aggregate (sources, stories, drafts, posts, ...)
 ├─ api/                FastAPI routers — thin, no business logic (per brief's anti-pattern list)
 └─ workers/            Celery tasks — discovery, embedding, generation, publishing, metrics, learning
        │
        ▼
Postgres 16 + pgvector  (schema in D, adapted from TRD §2 almost verbatim)
        │
        ▼
Redis (Celery broker + cache + rate-limit counters)
```

**Why keep `automation/*.py` logic instead of rewriting:** `persona.py` is pure (no I/O), already has a
passing self-test, and its formula is byte-for-byte the TRD formula. The refactor is *packaging*
(module → typed service class + Postgres-backed repository), not *rewriting the algorithm*. This is the
brief's own rule #29 ("when existing code solves a problem well, reuse it") applied literally.

**What changes from the TRD's stack notes:** the TRD says "GitHub Actions cron" is an acceptable
stand-in for Celery in the interim CLI version. For the production platform, replace it with Celery +
Redis as the brief requires (async, retryable, doesn't block web requests) — but the *cadence* stays
identical (discovery every 3h, publish check hourly, learning weekly) since that cadence was already
tuned to source refresh rates and content velocity.

---

## C. Existing Code Reuse Map

| Target platform piece | Reuse from | Reuse level |
|---|---|---|
| Scoring Agent | `persona.py::score_story` + all `*_score` functions | Port almost 1:1 into `domain/scoring.py`, add pydantic types, keep the self-test as a pytest file |
| Clustering Agent (lexical pass) | `persona.py::cluster_stories`, `similarity`, `_tokens`, `_stem` | Reuse as the cheap pre-filter; add pgvector cosine similarity as the authoritative pass (TRD §4 already specifies this hybrid) |
| Fact Verification Agent (deterministic part) | `persona.py::fact_confidence` | Reuse formula exactly; add an LLM pass for claim-level cross-checking (TRD names Claude Sonnet for this) |
| Safety Agent (deterministic gate) | `persona.py::classify_approval`, `violates_personal_experience_rule` | Reuse exactly — this is the "LLM must not control the hard gate" logic the brief demands; keep it rule-based, not LLM-based, for the final level assignment |
| Angle / Insight / Writer Agents | `generate_posts.py::news_prompt`, `idea_prompt`, `build_system_prompt` (in `persona.py`) | Split the single combined prompt into three sequential calls per the TRD agent table; reuse the prompt *content* (rules, insight questions, voice) almost verbatim — it's well-written and matches persona-spec.md exactly |
| Opportunity Agent | `persona.py::detect_opportunities`, `OPPORTUNITY_RULES` | Reuse as the rule-based first pass; TRD marks this "Claude Sonnet" for the production version — keep rules as a pre-filter to cut LLM calls |
| Trend Agent | `persona.py::detect_trends` | Reuse the bucketing logic; this is currently a simple pillar-count heuristic — fine as v1 |
| Report Agent | `news_engine.py::weekly_report` | Reuse the template structure; currently pure string templating (no LLM) — matches TRD's "Claude Sonnet" suggestion only loosely, acceptable to keep template-based for v1 |
| Memory Agent | `persona.py::is_repeat`, `similarity` | Reuse; upgrade to pgvector similarity against `posts.embedding` once that table exists |
| Learning loop | `feedback.py` in full (`compute_weights`, `clamp`, `performance_by_pillar`, `approval_by_pillar`) | Reuse exactly — floors/caps (0.7–1.4), min-sample gating, and the perf/approval blend already match TRD §10's formula |
| Publishers | `publish.py::post_twitter`, `post_linkedin`, `PUBLISHERS` dict | Reuse as the starting point for `services/publishing/`; add token refresh, idempotency keys, retry/backoff, and Instagram Graph API (currently unimplemented) |
| Source list | `automation/sources.yml` (17 pre-scored RSS feeds) | Load directly into the `sources` table on first migration |
| Persona/facts config | `profile/persona.yml`, `profile/facts.yml` | Seed `persona_config`, `interests`, `pillars`, `knowledge_items` tables from these on first migration; keep the YAML files as the human-editable export/import format for Settings |
| Voice/prompt rules | `persona-spec.md` §28–37 | Already encoded in `persona.yml → voice/safety` — reuse as-is |

**Net effect:** roughly 60–70% of the *domain logic* code for Scoring, Clustering (lexical), Safety,
Learning, and Publishing-gate agents can be ported with light typing changes, not rewritten. The genuinely
new code is: the web layer, the database layer, the four LLM agents that don't yet exist as separate
calls (Verify, Angle, Insight split from Writer), OAuth/token lifecycle, and all UI.

---

## D. Database Plan

Adopt TRD §2 (Postgres 16 + pgvector) essentially as written, with naming aligned to the brief's own
table list where the brief names something TRD didn't (`raw_articles` vs TRD's `stories` — same entity,
brief's name is clearer, used below). Differences from TRD called out explicitly.

```sql
-- ═══ Persona & knowledge (seeded from profile/*.yml on first migration) ═══
persona_config       (id, version, config JSONB, active, updated_at)
knowledge_items       -- profile/facts.yml, exploded to rows (kind, title, body, is_public, confidence, embedding)
pillars               (key PK, label_ar, label_en, target_share, multiplier)
interests             (id, name, tier, aliases[], pillar FK, enabled)

-- ═══ Sources & intelligence ═══
sources               (id, name, url, kind, source_type, credibility, region, enabled, last_fetched_at, failure_count)
raw_articles           -- TRD's "stories" — one row per fetched item, embedding VECTOR(1024), scores JSONB, relevance NUMERIC
story_clusters         (id, headline, primary_article_id, source_count, fact_confidence, key_facts JSONB, conflicts JSONB)
trends                 (id, pillar FK, headline, article_ids UUID[], strength, detected_at)
content_opportunities   -- brief's explicit name for TRD's opportunity output; one row per detected opportunity, FK to cluster

-- ═══ Content & approval ═══
ideas                  (id, title, pillar FK, angle, source_article_id, status)
drafts                 -- TRD's "posts" before approval; brief wants this split out explicitly as its own table
published_content      -- brief's explicit name; same row as draft once status flips to posted, or a separate
                        -- table keyed 1:1 to drafts.id — TBD in D1 below (open question)
approval_decisions      -- TRD's "approvals": decision, edit_diff, reason_tags[], decided_by, decided_at
performance_metrics     -- TRD's "post_metrics": impressions/likes/comments/shares/saves/profile_visits/followers/engagement_rate
learning_weights        -- TRD's table, unchanged: historical snapshots of pillar_multipliers JSONB
pillar_distribution     -- brief's explicit table: rolling actual-vs-target share per pillar, feeds the
                        -- Performance & Learning screen's "mix drift" view (TRD §12 acceptance criterion 8)
system_config           -- brief's explicit table: auto_publish_green, require_approval, timezone, thresholds override
audit_log               (actor, action, entity, entity_id, payload JSONB, created_at) -- unchanged from TRD
```

**D1 — open question, not decided silently:** the brief lists `drafts` and `published_content` as two
separate tables; TRD models this as one `posts` table with a `status` enum (`draft → approved → scheduled
→ posted`). Splitting into two tables duplicates most columns and needs a migration step on publish.
**Recommendation:** keep TRD's single `posts` table with status enum (simpler, matches how `queue.csv`
already works, avoids duplicate-row drift) — call it `drafts` in the API/dashboard layer when
`status IN ('draft','pending_review')` and `published_content` when `status = 'posted'`, via a view. Flagged
in K for explicit confirmation since the brief named them as distinct tables.

**Indexes:** `raw_articles(relevance DESC, published_at DESC)`, HNSW on both `raw_articles.embedding` and
`posts.embedding` (cosine ops), unique on `raw_articles.url`, unique on `sources.url`, composite index on
`posts(status, scheduled_for)`, GIN on `approval_decisions.reason_tags`.

**JSONB usage kept minimal per the brief's rule:** only for genuinely variable-shape data — `key_facts`,
`conflicts`, `scores` (7 named components, could be columns but change together and are always read as a
unit), `config` in `persona_config`. Everything else typed columns.

---

## E. Agent Architecture

11 agents, matching the brief's list 1:1 with TRD §3's table (same set, brief uses slightly different
names for 3 of them — mapped below). Each agent is a Python class/function with pydantic `Input`/`Output`
models, no direct DB or network access except what its contract explicitly allows, logged with
model+version+latency+cost metadata, called from `services/` (never from `api/` routers or from the
dashboard directly).

| Brief's name | TRD's name | Model | Deterministic guard | New or reused |
|---|---|---|---|---|
| Scoring Agent | Relevance Agent | Algorithmic (no LLM in v1) | N/A — pure math, already deterministic | **Reused** from `persona.py::score_story` |
| Clustering Agent | Dedup/Cluster Agent | Vector similarity + algorithmic; LLM only to resolve borderline cases | Cosine threshold hard-coded, not LLM-decided | **Reused** (lexical) + new (vector) |
| Verify Agent | Fact Verification Agent | Claude Sonnet | Output must cite `key_facts`; any number not traceable is stripped by deterministic post-processing, never by the LLM itself | New (deterministic half reused from `fact_confidence`) |
| Angle Agent | Angle Agent | Claude Sonnet | One angle only — enforced by schema (`angle: str`, not `list[str]`) | New (currently folded into `news_prompt`) |
| Insight Agent | Insight Agent | Claude Opus (higher reasoning budget — this is the highest-value, hardest-to-fake output) | Must answer one of the 8 `insight_questions` — validated by a required `question_answered` enum field in the output schema | New (currently folded into `news_prompt`) |
| Writer Agent | Writer Agent | Claude Sonnet | Platform length/structure rules enforced deterministically after generation (truncate/reject, not re-prompt-and-hope) | New (currently folded into `news_prompt`) — reuse platform specs from `persona.yml → platforms` |
| Safety Agent | Safety Agent | Deterministic rules **first**; Claude Sonnet only as an additional flag-raiser, never able to *lower* a level | Red flags, first-person-claim check, fact-confidence thresholds — all pure functions, LLM cannot override | **Reused** almost entirely from `classify_approval` |
| Memory Agent | Memory Agent | Vector similarity (pgvector) | Similarity ≥ 0.62 on hook/argument blocks auto-publish path, forces review | **Reused** logic, new storage (pgvector vs in-process list) |
| Opportunity Agent | Opportunity Agent | Rule-based first pass; Claude Sonnet for narrative labeling | Rules from `OPPORTUNITY_RULES` gate which clusters even reach the LLM | **Reused** (rules) + new (LLM narrative) |
| Trend Agent | Trend Agent | Algorithmic bucketing; Claude Opus only for the weekly narrative | Trend *detection* stays deterministic; only the write-up is LLM | **Reused** (detection) + new (narrative) |
| Report Agent | Report Agent | Claude Sonnet for prose sections; template for structure | Section skeleton from `weekly_report()` stays fixed | **Reused** (template) + new (prose polish) |

**Contract shape (all agents):**
```python
class AgentInput(BaseModel):
    ...  # agent-specific, always includes trace_id

class AgentOutput(BaseModel):
    ...  # agent-specific
    model: str          # e.g. "claude-sonnet-5"
    model_version: str  # API response's model field, not assumed
    latency_ms: int
    trace_id: str
```
Each agent: validates input against schema → calls LLM (or pure function) → validates output against
schema → on validation failure, retries once with a stricter instruction, then raises (never silently
passes through unvalidated text) → logs structured JSON (no secrets, no raw article bodies beyond a
truncated excerpt) → returns typed output. Deterministic business decisions (final safety level,
publish/no-publish, DB writes) happen **only** in the calling service, never inside the agent — this is
the brief's rule 16 applied literally: "LLMs must not directly control critical business operations."

---

## F. UX / User-Flow Plan

Design tokens seeded from the existing site (F0), then the 6 journeys the brief lists, mapped to the 5
screens from TRD §9 (already named "Today's Intelligence / Content Opportunities / Yahya Content /
Performance & Learning / Settings" — brief renames screen 3 to "Drafts & Approval", same screen).

**F0 — Design tokens (from `site/index.html`):** ink `#1a1a2e`, accent `#0f6b5c`, bg `#fafaf7`, muted
`#5a5a6e`, system font stack, RTL-first with an AR/EN toggle already proven to work — the dashboard
should reuse this exact toggle pattern (not rebuild i18n from scratch) and the same restrained,
single-accent-color, no-gradient aesthetic.

**F1 — Journey → screen mapping:**

| Journey (brief §27) | Screen(s) | Key interaction |
|---|---|---|
| 1. Open dashboard → today's intelligence → opportunity → draft | Today's Intelligence → Content Opportunities → Drafts | Click a story card's "Generate Draft" → jumps straight into the Drafts queue filtered to that opportunity |
| 2. Open Drafts → review → approve → auto-advance | Drafts & Approval | This is the money screen — see F2 |
| 3. Edit → feedback → save → continue | Drafts & Approval (inline edit, not a modal) | Edit box expands in place; reason chips (`tone`, `inaccurate`, `off-brand`, `repetitive`, `sensitive`, `weak-insight` — already defined in TRD's `reason_tags`) attach to the edit before advancing |
| 4. Reject → reason → save → continue | Drafts & Approval | Same reason-chip set; reject never requires a modal, one click + one chip + auto-advance |
| 5. View performance → understand learning | Performance & Learning | Plain-language framing per brief's UX bar — "AI + Construction posts are getting 34% higher engagement" not "engagement_rate: 0.034" |
| 6. Manage knowledge → facts update → future content improves | Settings → Knowledge | Direct edit surface over `knowledge_items`; explicitly closes the loop back to `profile/facts.yml`'s TODOs (university, years of experience, one project figure, one failure story) — filling these unlocks the highest-trust content type per `content_rules` |

**F2 — Drafts & Approval, in detail (the brief marks this "highest priority"):**

- List/inbox layout, not a form. One compact card per draft: platform icon, hook/first line, relevance
  badge (plain-language: "High relevance" not "87.3"), safety badge (green/yellow/red dot + one-line
  reason), pillar tag.
- Click (or `→`/arrow keys) expands the card in place to show: full content, source links, "why this was
  recommended" (2 lines max), Yahya-perspective summary, suggested edits if any — advanced JSON-ish detail
  (raw scores, similarity numbers, model name) behind a collapsed "Details" disclosure, never shown by
  default, per the brief's "no LLM jargon" rule.
- Sticky bottom action bar: Approve · Edit · Reject · Regenerate hook · Regenerate angle, plus progress
  counter "4 of 10 reviewed".
- Keyboard: `A` approve, `E` edit, `R` reject, `→`/`N` next, `←` previous. Approve/Reject auto-advance to
  the next unreviewed draft — never closes back to a list view and forces a re-open.
- Red-level drafts render with the same card shape but the Approve button is replaced with a disabled
  state plus "Requires explicit sign-off" — clicking it opens a one-line confirmation, not a full modal,
  consistent with TRD §6's "no auto-publish for red, ever, in any code path."

**F3 — What NOT to build (per brief §28):** no chart-heavy Performance screen by default (start with 4–5
plain-language stat cards + one trend line, add charts only where a single number can't say it), no
per-story raw JSONL dump anywhere in the UI, no settings screen that exposes the full `persona.yml` as a
YAML text box (build structured forms over the same fields — interests, thresholds, pillars — instead).

---

## G. 13-Week Implementation Plan

Maps the brief's 6 phases onto weeks, respecting TRD §13's phase durations (which sum to 13 weeks
already — a strong signal the TRD's estimates are the right starting point, reused rather than
re-derived).

| Weeks | Phase | Scope | Exit criteria |
|---|---|---|---|
| 1–2 | **Foundation** | Postgres+pgvector schema (D) stood up; migrate `sources.yml`, `persona.yml`, `facts.yml` into seed data; port `persona.py` scoring/clustering/fact-confidence into typed `domain/` services with a pytest suite (not just the inline self-test); FastAPI skeleton + auth | `pytest` green; `alembic upgrade head` reproducible; discovery cycle writes to `raw_articles` instead of JSONL |
| 3–4 | **Agents** | All 11 agents implemented per E, each with its own test file using recorded/mocked LLM fixtures (brief's testing rule); Verify/Angle/Insight/Writer split out of the current combined prompt | Each agent independently callable and testable; a full news→draft run produces the same *quality* of output as today's `generate_posts.py --from-news`, verified by side-by-side comparison on 10 real clusters |
| 5–7 | **Dashboard & Approval** | Next.js app, 5 screens, Drafts & Approval screen built first and iterated hardest (brief's stated priority); design tokens from F0; keyboard-shortcut review flow | Yahya (or a proxy tester) reviews 10 seeded drafts in ≤5 minutes in a usability pass |
| 8–9 | **Publishing & Integrations** | X, LinkedIn, Instagram OAuth + publishing services with token refresh, idempotency keys, retry/backoff; TikTok stays manual (brief confirms this) | A test draft published to all 3 platforms from the dashboard; a forced-retry test proves no duplicate post |
| 10–11 | **Measurement & Learning** | Metrics polling jobs (replace manual `performance.csv`) for X/LinkedIn/Instagram insights APIs; port `feedback.py` learning-weight computation into a Celery weekly job; Performance & Learning screen wired to real data | Weight computation matches `feedback.py`'s existing formula output on the same fixture data (regression test) |
| 12 | **Intelligence depth** | Trend/Opportunity agents' LLM narrative layer; weekly report auto-generated and surfaced in-dashboard (not just a markdown file) | Weekly report acceptance criteria from TRD §12 item 6 pass |
| 13 | **Hardening & launch prep** | Security pass (E1 below), load/perf check against TRD §12's targets (1000+ articles/day, 10–20 drafts/day, <5% false-positive relevance), `auto_publish_green` stays `false` (brief rule 5 — non-negotiable for the first 3 months regardless of platform readiness) | Acceptance criteria in TRD §12 all green; security checklist (I below) signed off |

Each week ends with: what changed, tests run, regressions checked, what remains — per the brief's own
"for every major implementation step" reporting rule.

---

## H. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `facts.yml` TODOs stay unfilled | High (already true today) | High — blocks the highest-trust content type (personal experience posts); Safety Agent will correctly keep flagging first-person claims red without them | Settings → Knowledge screen (F1, journey 6) makes filling these a 5-minute dashboard task instead of a YAML edit; block nothing else on this |
| LinkedIn/Instagram API access approval delays | Medium-High | Medium — Instagram Graph API and LinkedIn Marketing API both require app review / business verification that only Yahya's business entity can complete, not something this build can do on his behalf | Sequence X first (fastest to approve), keep Instagram as `manual` output (already the pattern in `publish.py`) until access is granted; flagged as an open question in K |
| Semantic clustering false-merges or false-splits distinct events | Medium | Medium — brief's core rule ("one event = one post") breaks if wrong | Keep the lexical pre-filter as a floor (already tested), add pgvector as the primary signal, tune threshold against a labeled sample of ~50 real clusters before trusting it unattended |
| Auto-publish gets enabled prematurely | Low (explicit config default is `false`) | Very High — violates brief rule 5 directly | `auto_publish_green` hard-coded `false` in `system_config` seed; changing it requires an explicit, logged, dated admin action, not a silent default flip; add a CI check that fails the build if the default seed value is ever `true` |
| Shared VPS resource contention (13.140.138.252 already runs ~40 other containers) | Medium | Medium — Postgres+Celery+Redis+FastAPI+Next.js is a heavier footprint than the current 2 lightweight containers | Confirm with the user whether this box is the intended target before provisioning (K) — a dedicated instance may be warranted given the box's existing load |
| Cost of Claude Opus calls (Insight/Trend agents) at 1000+ articles/day intake | Medium | Medium | Only clusters above `deep_dive` threshold (78) get Opus; everything else uses Sonnet or stays algorithmic — already the TRD's design, just needs cost monitoring dashboarded |
| Learning loop collapses content diversity | Low (brief's own floors/caps already specified and already implemented in `feedback.py`) | High if it happened | Reuse `feedback.py`'s existing 0.7–1.4 clamp and 5%-per-pillar floor unchanged; add a regression test that asserts no pillar can reach 0% share |

---

## I. Testing Strategy

- **Unit** (pytest): every function ported from `persona.py` (scoring components, clustering, fact
  confidence, approval classification) gets its own test file; `_self_test()`'s 10 assertions become the
  first 10 test cases, not replaced. Same for `feedback.py`'s weight computation and `mix_deficit`.
- **Agent tests**: each of the 11 agents tested against recorded fixture inputs/outputs (brief's
  "deterministic mocks/fixtures" rule) — no live Anthropic API calls in the test suite. A small "golden
  set" of 10–15 real story clusters (anonymized if needed) becomes the shared fixture base for Verify/
  Angle/Insight/Writer/Safety, so a prompt change can be diffed against known-good output.
- **Integration**: Postgres (testcontainers or a disposable schema), RSS ingestion against recorded feed
  fixtures (not live network in CI — `sources.yml`'s feeds change/break over time, exactly as the repo's
  own comments warn), social API clients against recorded HTTP fixtures.
- **E2E**: the exact flow the brief names — news → opportunity → draft → approval → publish → metrics —
  plus explicitly: reject, edit, regenerate, failed publish (assert retry doesn't double-post), red-content
  block (assert it is *impossible* to reach a published state from a red draft without an explicit signed
  approval row).
- **Security tests**: assert no API key/token ever appears in a log line (brief rule 21) — a log-scanning
  test over a captured run's output.

---

## J. Deployment Strategy

- **Containers**: extend the existing `Dockerfile.site` / `Dockerfile.automation` pattern — add
  `Dockerfile.api`, `Dockerfile.worker`, `Dockerfile.dashboard`; keep the same `deployment.md` style
  (build → save tar → load → run) that's already documented and already used successfully for the live
  site, so the deployment *muscle memory* stays consistent for whoever operates this.
- **docker-compose** extended with `postgres` (pgvector image), `redis`, `api`, `worker`, `dashboard`
  services, all on an internal network, only `dashboard` (and optionally `api`) exposed.
- **Secrets**: move off plaintext `config.yml` for anything beyond local dev — use environment variables
  injected at container run time from a secrets manager or, at minimum, the same GitHub Secrets → runtime
  env pattern the `publish.yml` workflow already uses, extended to all services.
- **Scheduling**: Celery beat replaces the two GitHub Actions cron workflows for the always-on production
  path; keep the GitHub Actions workflows as-is for now (they work, they're free, they're already proven)
  until the Celery/worker stack is live and verified, then retire them — no need to run both long-term.
- **Open item**: which host. See K.

---

## K. Open Questions / Assumptions

These are decisions the brief's own rule 29 says not to invent silently. Framework/algorithm choices
above (FastAPI, Next.js, Postgres+pgvector, Celery+Redis) are **not** listed here — they're the TRD's own
prior decision, already the right fit, adopted without re-litigating.

**Resolved (2026-08-31):**

1. **Hosting target — decided: same shared VPS (`13.140.138.252`).** Reuses the existing deployment
   pattern (docker-compose, tar-based image transfer, same ops muscle memory as the live site). Because
   this box already carries real load from ~40 other client containers, Phase 1 will size Postgres/Redis
   conservatively and J's docker-compose addition will pin resource limits per service rather than
   assuming headroom.
2. **Social platform developer accounts — decided: start now, in parallel with Week 1 engineering.** This
   requires Yahya personally (business identity/verification) — engineering cannot do this on his behalf.
   Concretely, three things need to start immediately and independently of any code in this repo:
   - X: apply for a paid Basic (or higher) API plan at developer.x.com under Yahya's business.
   - LinkedIn: register a Marketing API app at developer.linkedin.com/apps, request `w_member_social`
     access (this typically requires a use-case review).
   - Instagram: create/verify a Meta Business account, link an Instagram Business account to a Facebook
     Page, register a Meta App, and submit for App Review on the `instagram_content_publish` permission.
   Track these three as an external, non-blocking-for-engineering workstream; Phase 4 (Weeks 8–9) assumes
   at least X is approved by then, with Instagram/LinkedIn allowed to land later per item 6 below.
3. **`drafts` vs `published_content` — decided: one `posts` table with a status enum**, exposed to the
   API/dashboard as two logical views (`status IN ('draft','pending_review')` vs `status = 'posted'`).
   Matches the existing `queue.csv` pattern and avoids duplicate-row drift on publish. D1 above is now
   settled; the schema in D reflects this.

**Still open:**

4. **`facts.yml` TODOs** — university/graduation year, exact years of experience, one project figure, one
   failure-and-lesson story are still blank. These aren't a technical blocker (the Safety Agent correctly
   keeps first-person claims yellow/red without them) but they cap content quality on day one. Worth
   scheduling time with Yahya to fill these before or during Week 1, independent of engineering work.
5. **Budget appetite for paid news APIs.** TRD §5 lists NewsAPI/GNews/Bing ($50–500/mo) and GDELT (free)
   as optional expansions beyond the current free RSS-only setup. Starting RSS-only (current state) and
   adding paid feeds only if discovery volume proves insufficient against the "1000+ articles/day" target
   — recommend, not assumed as approved spend.
6. **Whether to build the Buffer/Typefully/Metricool fallback** (TRD §8.5) instead of direct platform
   APIs for Instagram specifically, given Meta's app-review friction — could unblock Instagram publishing
   weeks earlier than direct Graph API integration. Worth a decision once item 2's Instagram timeline is
   clearer.

---

*This document is the analysis deliverable requested before implementation begins. No code has been
written or modified as part of producing it. Next step, pending answers to K.1–K.2 in particular: begin
Phase 1 (Foundation) in small, verifiable increments as instructed — starting with the Postgres schema
and porting `persona.py` into a tested `domain/` module, since neither depends on the open hosting/API
questions above.*
