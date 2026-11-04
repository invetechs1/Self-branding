# Bringing the CLI Engine Into the Live Product
## Handoff guide for the developer — what is done, what is missing, what to build

**Audience:** the engineer maintaining `backend/` and `frontend/`
**Status of the live product:** the discovery → scoring → drafting → publishing loop works. Seven
capabilities the client asked for exist only in the `automation/` CLI and are not reachable from
the product.
**Reference implementation:** `automation/*.py` — working, tested (244 checks), runs without a
database. Where this guide and the CLI disagree, the CLI is the specification.

---

## 0. One thing first: rotate a credential

A plaintext password for the real account `yahya@bassir.net` is committed in three files:
`backend/scripts/create_user.py`, `backend/tests/test_auth_api.py`, `backend/tests/test_users.py`.

If that is the live login, change it now and treat it as exposed — it is in Git history, so anyone
with repository access has it. Then:

- move the seed credentials to environment variables (`SEED_USER_EMAIL` / `SEED_USER_PASSWORD`),
- use a throwaway password in tests, not the real one.

This is not about the current team; it is about the next person who clones the repo.

---

## 1. What has already been fixed — branch `claude/backend-saudi-first-scoring`

The backend had the new nine pillars and read the new weights from `persona.yml`, but not the
policy that makes them work. Measured on the client's own examples, with `pipeline_entry = 55`:

| Story | Score before | Score after |
|---|---|---|
| HRSD requires contractor labour contracts via Qiwa | 50.9 → filtered out | **85.6** |
| Riyadh infrastructure projects awarded to local contractors | 37.7 → filtered out | **87.0** |
| Jeddah municipality finds execution defects | 41.5 → filtered out | **73.9** |
| GOSI changes contribution calculation | 43.4 → filtered out | **66.2** |
| OpenAI launches enterprise AI agents (English) | 78.1 — the only one entering | 71.9 |

Before the fix the live engine admitted exactly one story out of seven, and it was the English one.
That is the client's original complaint, reproduced in code.

**Four gaps were closed**, all ported from the CLI so the engines cannot drift:

1. **`text.hits()` — Arabic matching.** Arabic glues prepositions onto words: `بالرياض` (in Riyadh),
   `للمقاولين` (for contractors). Stripping the standalone `ال` in `normalize()` does not reach those,
   so the most common written form of a keyword scored zero. Now prefix/suffix tolerant, and still
   rejects near-misses (`رياضة` does not match `الرياض`).
2. **`scoring.activity_hits()` — the six declared activities** from `persona.yml → saudi_activities`,
   ranked by match strength × activity weight. They also count as declared interest, so an Arabic
   ministry decision no longer scores 0 on `personal_interest`.
3. **`saudi_gcc_score()` — geography.** Government bodies are now a conclusive Saudi signal, and the
   source region settles it when the headline does not. `saudi_watchlist` is no longer used for
   geography: it lists *topics* ("Infrastructure", "Tourism"), not places, so any global story
   matching one looked Saudi and silently defeated the whole policy.
4. **`score_article()` — the `saudi_first` multipliers** (activity boost, global discount, AI
   exemption, Arabic preference) plus government-source pillar routing.

**Verify in two minutes:**

```bash
cd backend && pip install -r requirements-dev.txt
pytest tests -q                                  # 71 passed (was 55)
pytest tests/test_saudi_first_scoring.py -q      # the 16 new cases
```

Merge this branch before building anything below — every feature here assumes correct ranking.

---

## 2. What is missing from the product

Each item lists the CLI reference to port, what to build, and how to know it works.

### 2.1 Personal voice — the output does not sound like Yahya

**Reference:** `profile/voice-samples.md`, `automation/persona.py::load_voice`, `voice_block`
**Problem:** the writer agent produces correct but generic Arabic. The samples file exists; nothing
reads it.

Build:
- Parse the file (sections = samples, the YAML block = binding preferences).
- Inject into the writer/insight system prompt as a **style reference, not a fact source** — the CLI
  prompt says this explicitly; keep that wording, otherwise the model will quote the samples' facts.
- Cap the injected size (the CLI uses ~3200 chars) so prompts stay bounded.
- Surface it in Settings so Yahya can paste samples from the UI instead of editing a file.

Done when: an empty file changes nothing, and a filled file visibly changes tone in generated drafts.

### 2.2 Government decisions — the highest-value source is not collected

**Reference:** `automation/gov_watch.py`, `automation/gov_sources.yml`
**Problem:** eight Saudi bodies (HRSD, GOSI, Saudi Contractors Authority, ZATCA, MOMAH, MC, SBC,
SDAIA) publish the decisions Yahya's audience cares about, and none of them offers RSS. The CLI
scrapes their news pages; the backend only ingests RSS.

Build:
- A scraper service beside `services/discovery.py`, reusing `gov_watch.entity_items()`:
  explicit CSS selectors when configured, automatic list detection otherwise.
- **Charset handling matters:** these sites often omit `charset` from the HTTP header and declare it
  only in `<meta>`; `requests` then decodes Arabic as Latin-1 and every keyword silently fails to
  match. `gov_watch.fetch_html()` already handles this — port it, do not rewrite it.
- Store scraped items with `source_type = official_government` and `meta.gov_entity = <key>`; the
  scoring port already routes those to the `government_decisions` pillar.
- Admin UI: list entities, show last fetch time and item count, let Yahya paste a CSS selector when
  a site changes.

Done when: a scheduled run adds items from at least three bodies and they rank above global news.

### 2.3 Operational data stories — the only content nobody can copy

**Reference:** `profile/operations-metrics.yml`, `automation/data_stories.py`
**Problem:** Yahya's own operational numbers (payment cycle, change-order ratio, rework rate) are
the one content source competitors cannot reproduce. The product has no place to hold them.

Build:
- A `metrics` table + CRUD, mirroring the YAML fields: `key, label, value, unit, basis, period,
  sensitivity, angle`.
- **Port `data_stories.validate()` exactly — it is a safety boundary, not a nicety:** minimum
  aggregation of 5 cases, mandatory basis containing a number, absolute money amounts rejected in
  any field, `internal`/`never` never published.
- A generation mode using `data_story_prompt`, and force the approval level to at least **yellow**
  for this content type regardless of what the safety classifier says.

Done when: a metric with `basis: "من 3 مشاريع"` is refused with a reason, and a generated draft
never contains a number that is not in the record.

### 2.4 Saudi occasions calendar

**Reference:** `content/saudi-calendar.yml`, `automation/calendar_sa.py`
**Problem:** National Day, Founding Day, Flag Day, Ramadan and the two Eids are predictable content
windows that are currently missed. Hijri dates need Umm al-Qura conversion (`hijridate`).

Build: a daily job that surfaces occasions entering their lead window, a dashboard card, and a
generation mode using the professional angle stored per occasion (the rule is: no generic greetings).

### 2.5 Automatic metrics collection

**Reference:** `automation/fetch_metrics.py`
**Problem:** `performance` endpoints read metrics from the database; nothing writes them from the
platforms, so learning depends on manual entry and will stop within weeks.

Build:
- Scheduled pull: X (`public_metrics`, degrade gracefully when `non_public_metrics` is refused),
  TikTok (`/v2/video/query/`), LinkedIn (`/v2/socialActions/{urn}` — likes and comments only).
- **LinkedIn impressions are not available for personal profile posts.** Do not fake a zero: mark
  the row, let Yahya fill impressions manually, and never overwrite a manual value with an API zero
  (`fetch_metrics.merge()` does exactly this — port the rule).
- Requires storing the platform post id at publish time. The CLI added an `external_id` column for
  this; for X threads it stores the **head** tweet id, which is the one people open.

### 2.6 Inbound opportunities — the product measures the wrong thing

**Reference:** `outreach/inbound-log.csv`, `automation/attribution.py`
**Problem:** the stated objective is business opportunities, not followers, and nothing measures it.
`domain/learning.py` weights performance 70% and approvals 30%.

Build:
- An `inbound` table: date, channel, kind, opaque label, `source_post_id`, stage, weight (1–3).
  **No names, no phone numbers, no contract values** — the CLI warns on those patterns; keep the warning.
- Attribution report: which pillar produced opportunities, close rate, channels.
- **Change the learning blend to performance 40% / inbound 40% / approval 20%**
  (`attribution.inbound_signal`), with the guard that a pillar needs ≥2 opportunities before it
  moves any weight.

Done when: a pillar with opportunities outranks a pillar with likes in `pillar_multipliers`.

### 2.7 Reply radar

**Reference:** `content/reply-watchlist.yml`, `automation/reply_radar.py`
**Problem:** the strategy calls for ten considered replies a day; the product does nothing here, and
replies are what actually grow an X account.

Build: a daily shortlist scored by activity overlap × engagement velocity × recency, excluding
anything older than six hours, low-engagement, controversial, or already replied to. Show the angle;
let Yahya write the reply.

**Hard constraint:** never post a reply automatically. Automated replies breach platform terms and
synthetic replies are detected. The CLI enforces this structurally — the module contains no posting
function and imports no publishing layer, and two tests assert it. Keep that property.

### 2.8 Learned posting times (small, high value)

**Reference:** `automation/feedback.py::learn_post_times`, `persona.yml → posting`

`domain/learning.py` has `best_slots()` but nothing uses it, and schedule times are not derived from
it. Port the version with the guardrails: a slot is adopted only with ≥3 posts **and** only if it
falls inside the strategy's golden windows. A single post that did well at 3am must not become the
posting time.

---

## 3. Known issues to decide on

**Score cap destroys ranking resolution at the top.** `total = min(100, base × multiplier)`. With the
Saudi-first multipliers (up to ~1.55), any story with a base above ~65 pins at 100, so the strongest
stories become indistinguishable — exactly where ordering matters most. Options: keep the cap for
display but sort on the uncapped value, or compress above 100 instead of clipping. Changing this
diverges from the CLI, so decide for both and change them together.

**`government_watchlist` rarely matches.** Entries are full official names
("وزارة الموارد البشرية والتنمية الاجتماعية") which almost never appear verbatim in a headline.
Geography detection works today because `geography.terms.saudi_arabia` carries the short forms.
Consider adding short aliases per body, in both the CLI and the backend.

**RSS and scraped sources need verification on a machine with real network access.** Several Arabic
feed URLs have never been confirmed to work. `python automation/news_engine.py --check-sources`
prints the failure reason per feed; `python automation/gov_watch.py --check` does the same for the
government pages.

---

## 4. Suggested order

1. Merge `claude/backend-saudi-first-scoring` — everything else depends on correct ranking.
2. Rotate the committed credential (§0).
3. §2.2 government scraping — the biggest content gap, and uniquely defensible content.
4. §2.1 voice samples — the cheapest change with the most visible effect on output quality.
5. §2.5 + §2.6 metrics and inbound — without them the learning loop is decorative.
6. §2.3, §2.4, §2.7 — data stories, occasions, reply radar.
7. §2.8 posting times — an afternoon's work.

---

## 5. A principle worth keeping

Three rules in the CLI are enforced in code rather than trusted to prompts, because each one protects
the client's reputation:

- **No fabricated personal experience.** Personal facts come only from `profile/facts.yml`.
- **No automated replies**, ever.
- **Operational data never publishes without human review**, whatever the classifier says.

Where the product reimplements a behaviour, port the enforcement too — not just the feature.
