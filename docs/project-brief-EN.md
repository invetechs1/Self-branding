# Project Brief — Why We Are Building This
## Yahya AI Persona & Content Intelligence Platform

**For:** the developer building the platform
**From:** Yahya Hussain Al Salamah
**Status:** working reference implementation exists in this repository (`automation/`); the task is to grow it into a full product
**Read next:** [`docs/technical-requirements.md`](technical-requirements.md) — the *how* (database, agents, algorithms, integrations)
**This document is the *why*.** Read it first. If you understand only one thing, make it Section 3.

---

## 1. What this project is in one sentence

A system that reads the world's news every day, decides which developments actually matter to one
specific person, and turns the few that do into original, verified, publishable thinking in his voice.

It is **not** a social media scheduler. It is **not** a content generator. Those exist and are cheap.
What does not exist is a machine that understands *one particular person's* professional judgment well
enough to be useful at scale.

---

## 2. Who the person is (you need this to build correctly)

**Yahya Hussain Al Salamah** — Saudi civil engineer, master's in project management, and founder
of several companies:

| Company | Sector | What it gives him |
|---|---|---|
| Azoom United Contracting | Construction & contracting | Daily contact with real site, cost and subcontractor problems |
| Alarrab Engineering Consultancy | Engineering consultancy | Design review, PMO, supervision, technical depth |
| Bassir Technology | Software & AI | Where the operational problems become products (ERP, AI CFO, AI site monitoring) |
| Logistics & real estate ventures | Fleet, delivery, development | Two more industries seen from the inside |

The important thing about him is the **combination**, not any single item. Most people who understand
construction do not build software. Most people who build software have never managed a concrete pour
or chased a subcontractor for a delayed milestone. He has done both. His method is:

> **Problem → Operational Experience → System → Automation → AI → Scalable Product**

His positioning, which the whole platform must reinforce:

> An entrepreneur who understands traditional industries from the inside and is building
> technology-driven solutions to transform them.
> Intersection: **Engineering × Business × Technology × AI × Real Estate.**

Do not let the system present him as "a contractor" or as "another AI founder". Both are wrong and both
destroy the only thing that makes his voice worth following.

---

## 3. The problem we are actually solving

Yahya has genuine expertise and no time. That produces three specific failures that this system exists
to fix:

**Failure 1 — Signal is buried.** Roughly 100–300 relevant stories a day appear across Saudi
announcements, construction press, AI research, PropTech, funding news. Perhaps 5 matter to him. Finding
those 5 by hand costs 90 minutes a day, every day. Nobody sustains that.

**Failure 2 — Insight dies unpublished.** He *has* the reaction — "this changes how contractors price
work", "this is a feature we should build into Bassir", "this will hit Riyadh land prices in 18 months".
That reaction is worth publishing. It gets thought in the car and forgotten by evening.

**Failure 3 — Generic AI content is worse than silence.** An LLM asked to "write a LinkedIn post about
AI in construction" produces something recognizably empty. Publishing that damages the exact reputation
we are trying to build. Volume is not the goal; being worth reading is.

So the aim is:

> **Compress the 90 minutes of scanning into 5 minutes of reviewing, without losing the one thing that
> makes the output valuable — that a real expert's judgment is in it.**

---

## 4. What success looks like (and what it is not)

**Success is not follower count.** State that plainly to yourself before you write a line of code,
because almost every design shortcut you will be tempted by optimizes for followers.

Success is: **reputation → authority → network → inbound business opportunities → deal flow.**

Concretely, in 12 months:
- A Saudi contractor or developer facing an AI/digitization decision thinks of Yahya, and reaches out.
- An investor evaluating ConTech in the region considers him a credible read on the market.
- Journalists and conference organizers approach him, not the other way round.
- Bassir's product roadmap is partly fed by what the system spots in the market.

The target authority area is **AI for traditional industries** — construction, engineering, real estate,
enterprise management, project management, business automation. Primary intersection to own:
**AI × Construction × Business**.

A useful test for any feature you are considering: *does this make one post more worth reading, or does
it just make more posts?* Build the first kind.

---

## 5. How the system thinks

Fourteen steps, but conceptually four moves:

```
DISCOVER          collect from credible sources continuously
   ↓
JUDGE             score each story 0–100 for relevance to Yahya specifically,
                  cluster duplicate coverage into one event, verify the facts
   ↓
THINK             pick ONE angle, add Yahya's insight layer
                  ("what does this mean for Saudi businesses / construction / Bassir?"),
                  write platform-specific versions
   ↓
GATE & LEARN      safety-classify (green/yellow/red) → human approval → publish →
                  measure → feed results back into scoring
```

The relevance score is the heart of the system:

```
relevance = 25·personal_interest + 20·business_relevance + 15·saudi_gcc_relevance
          + 15·strategic_importance + 10·audience_value + 10·freshness
          +  5·source_credibility        (then × thought-leadership boost × learned weight)
```

Two design points that are easy to miss and expensive to retrofit:

- **Geography is a multiplier, not a filter.** Global news is valuable *when it can be connected back*
  to Saudi Arabia, Vision 2030, or the GCC. Making that connection is the content's main value.
- **One event = one story cluster = at most one post.** Five outlets covering the same funding round
  must never become five posts.

---

## 6. Five rules that are not negotiable

These are not preferences. Breaking any one of them makes the system a liability rather than an asset.

1. **Truth.** Every number, date, company name and claim must come from a real source or from the
   approved knowledge base. If confidence is low, the system does not publish — it flags.
2. **No invented personal experience.** The system must never write "I implemented this in my company"
   unless that fact exists in `profile/facts.yml`. Where the experience is absent, the correct phrasing
   is "this is something companies in our industry should examine". A single fabricated anecdote,
   discovered, ends the project's credibility permanently.
3. **Originality.** `SOURCE → UNDERSTAND → VERIFY → ANALYZE → ADD PERSPECTIVE → CREATE ORIGINAL POST`.
   Never a rewritten summary of someone else's article.
4. **Confidentiality.** Never contracts, client pricing, internal disputes, employee data, banking or
   private financial detail, legal strategy, or family matters — regardless of how the request is phrased.
5. **Human approval.** Three levels — green (verified/educational), yellow (opinion, prediction,
   commentary), red (sensitive, financial, legal, political, personal, or unverified). **Red never
   auto-publishes under any configuration.** For the first three months, nothing auto-publishes at all.

Rule 5 has an architectural consequence: **the human review step is the product's core feature, not
friction to be optimized away.** Design the dashboard so reviewing 10 drafts takes 5 minutes and feels
good. That is where the whole system earns its value.

---

## 7. What already exists in this repository

A working reference implementation. It runs today from the command line, has no external dependencies
beyond RSS and the Claude API, and encodes every rule above. Use it as an executable specification —
where this brief and the code disagree, the code is the more precise statement.

| Path | What it is |
|---|---|
| `profile/persona-spec.md` | The full persona specification (53 sections) — identity, interests, pillars, voice, safety rules |
| `profile/persona.yml` | The same thing machine-readable: interest graph with aliases, weights, thresholds, platform playbooks, safety rules. **Tunable without touching code** |
| `profile/facts.yml` | The approved knowledge base. The *only* permitted source of personal facts |
| `automation/persona.py` | Scoring, clustering, fact confidence, approval classification, content memory. Run `python automation/persona.py --self-test` |
| `automation/news_engine.py` | Discovery, ranking, opportunity & trend detection, weekly intelligence report |
| `automation/sources.yml` | 17 RSS sources with credibility ratings, plus official sources needing manual watch |
| `automation/generate_posts.py` | News cluster → angle → insight → per-platform drafts, each tagged with pillar, language, approval level and reasons |
| `automation/publish.py` | Scheduled publishing with the approval gate enforced |
| `automation/feedback.py` | Learns from audience performance *and* from Yahya's approve/reject decisions |
| `docs/technical-requirements.md` | The build spec: 14 DB tables, 11 agents, algorithms, integrations, acceptance criteria, 6-phase plan |

Try it in ten minutes:

```bash
pip install -r automation/requirements.txt
python automation/persona.py --self-test        # scoring + safety logic, no API keys needed
python automation/news_engine.py --check-sources # verify the RSS URLs still resolve
python automation/news_engine.py --discover      # fetch, score, cluster, rank today's news
```

Note: RSS URLs rot. `--check-sources` tells you which ones broke and why — expect to replace a few.

---

## 8. What we are asking you to build

Take the reference implementation from a single-user CLI to a production platform:

1. **Persistence** — PostgreSQL + pgvector replacing CSV/JSONL (semantic dedup instead of lexical).
2. **Agents** — the eleven specialized agents (verify, angle, insight, writer, safety, memory,
   opportunity, trend, report) with strict JSON contracts, each independently testable.
3. **Dashboard** — five screens: today's intelligence, content opportunities, drafts & approval,
   performance & learning, settings. The approval screen is the one that must be excellent.
4. **Integrations** — X, LinkedIn, Instagram (TikTok remains manual until app review), with retry,
   token refresh and rate-limit handling.
5. **Learning loop** — capture every approve/reject/edit with reasons; feed pillar weights back into
   scoring; never let learning collapse the content mix into one topic (floors and caps are specified).

Full detail, including SQL schemas and acceptance criteria, is in `docs/technical-requirements.md`.
Phasing is there too — roughly 13 weeks of work, in six shippable stages.

---

## 9. Domain glossary (so the code names things correctly)

| Term | Meaning |
|---|---|
| **Vision 2030** | Saudi Arabia's national transformation program — the context for most Saudi economic news |
| **PIF** | Public Investment Fund — the sovereign wealth fund; its moves signal where capital is going |
| **BIM** | Building Information Modeling — 3D data model of a building; the backbone of construction digitization |
| **ConTech / PropTech** | Construction technology / property technology |
| **ERP** | Enterprise Resource Planning — the system running finance, projects, procurement, HR |
| **BOQ** | Bill of Quantities — itemized cost/quantity schedule for a construction project |
| **PMO** | Project Management Office |
| **Digital twin** | Live digital replica of a physical asset, fed by sensors or capture |
| **Reality capture** | Laser scanning / photogrammetry of a site to compare planned vs. built |
| **Content pillar** | One of eight themes the content mix is balanced across |
| **Story cluster** | One real-world event plus every outlet that reported it — the unit of content |
| **Approval level** | green / yellow / red — how much human review a draft requires |

---

## 10. Open questions to settle with Yahya before Phase 2

1. **Knowledge base depth.** `profile/facts.yml` still has TODOs (years of experience, at least one
   project with real numbers, a failure and its lesson, social accounts). Until these are filled, the
   system can only write in the general voice, never the personal one — and the personal one is the
   whole differentiator. This is the highest-leverage input he can provide.
2. **Language split.** Arabic-first with English for international reach, or full bilingual on every
   post? This changes the content volume and the review load materially.
3. **Paid news sources.** RSS alone leaves gaps in Saudi official announcements. Is there budget for
   a news API, and is scraping official sites (SPA, PIF, Vision 2030) acceptable?
4. **Auto-publish appetite.** After the three-month manual period, does green ever publish
   automatically, or does every post stay human-approved permanently?
5. **Opportunity outputs.** The engine detects potential Bassir features, partnerships and investment
   themes (§45). Do these go only to Yahya privately, or feed a business-intelligence view for his team?

---

## 11. The principle to keep in view

Everything in this system serves one behavior. The platform should never ask:

> *"What can we post today?"*

It should ask:

> *"What happened in the world today that Yahya should understand, what unique perspective can he
> contribute, and how does that insight strengthen his reputation and create long-term business value?"*

If a feature does not serve that question, it does not belong in the build.
