"""Discovery service — orchestrates the network/IO side of TRD § 38 steps 1-6:
    fetch RSS -> dedupe against stored articles -> score -> filter by threshold
    -> cluster -> persist.

Ported from ``automation/news_engine.py``'s ``fetch_feeds``/``discover``, now
calling into the typed ``app.domain`` functions and Postgres repositories
instead of ``feedparser`` writing to a JSONL file directly. Kept in
``services/`` (not ``domain/``) because it performs network IO, matching the
brief's own service list ("discovery, scoring, clustering, generation, safety,
publishing, learning").

RSS fetching accepts an injectable ``parse_fn`` so tests never hit the network
(brief's testing rule: "RSS ingestion against recorded feed fixtures, not live
network in CI") — production code just omits it and gets ``feedparser.parse``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.domain.clustering import cluster_articles
from app.domain.models import Article
from app.domain.opportunities import detect_opportunities
from app.domain.scoring import score_article
from app.repositories.articles import RawArticleRepository
from app.repositories.clusters import StoryClusterRepository
from app.repositories.opportunities import OpportunityRepository
from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository

USER_AGENT = "Mozilla/5.0 (compatible; YahyaBrandEngine/1.0; +personal content research)"


class FeedSpec(BaseModel):
    source_id: int
    name: str
    url: str
    source_type: str
    region: str | None = None


@dataclass
class FetchOutcome:
    source_id: int
    name: str
    count: int
    error: str | None = None


@dataclass
class DiscoveryResult:
    fetched: int = 0
    new: int = 0
    kept: int = 0
    clusters: int = 0
    feed_outcomes: list[FetchOutcome] = field(default_factory=list)


def _parse_date(entry: dict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_feeds(feeds: list[FeedSpec], limit_per_feed: int = 25,
                parse_fn: Callable | None = None) -> tuple[list[Article], list[FetchOutcome]]:
    """Reads every feed; one feed failing never stops the rest (same resilience
    rule as the CLI reference)."""
    if parse_fn is None:
        import feedparser
        parse_fn = lambda url: feedparser.parse(url, agent=USER_AGENT)  # noqa: E731

    articles: list[Article] = []
    outcomes: list[FetchOutcome] = []
    for feed in feeds:
        try:
            parsed = parse_fn(feed.url)
        except Exception as e:  # noqa: BLE001 — one broken source must not stop the cycle
            outcomes.append(FetchOutcome(feed.source_id, feed.name, 0, str(e)[:200]))
            continue

        entries = getattr(parsed, "entries", None) or parsed.get("entries", [])
        if not entries:
            outcomes.append(FetchOutcome(feed.source_id, feed.name, 0, "empty feed"))
            continue

        for entry in entries[:limit_per_feed]:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            articles.append(Article(
                title=title, summary=(entry.get("summary", "") or "")[:600],
                url=entry.get("link", ""), source=feed.name, source_type=feed.source_type,
                published=_parse_date(entry), meta={"feed_region": feed.region or "global"},
            ))
        outcomes.append(FetchOutcome(feed.source_id, feed.name, min(len(entries), limit_per_feed)))

    return articles, outcomes


def run_discovery_cycle(session: Session, *, limit_per_feed: int = 25,
                        threshold: float | None = None, now: datetime | None = None,
                        parse_fn: Callable | None = None) -> DiscoveryResult:
    """The full cycle, transactional: caller commits (or rolls back) after this
    returns — this function only flushes, never commits, matching the "no hidden
    state transitions" / explicit-transaction-boundary principle."""
    now = now or datetime.now(timezone.utc)
    persona_repo = PersonaRepository(session)
    persona_config = persona_repo.get_active_persona_config()
    if persona_config is None:
        raise RuntimeError("no persona_config in database — run scripts/seed.py first")
    persona = persona_config.config
    threshold = threshold if threshold is not None else persona["thresholds"]["pipeline_entry"]
    learning = {p.key: float(p.multiplier) for p in persona_repo.list_pillars()}

    source_repo = SourceRepository(session)
    sources = source_repo.list_enabled()
    feeds = [FeedSpec(source_id=s.id, name=s.name, url=s.url, source_type=s.source_type,
                      region=s.region) for s in sources]

    fetched, outcomes = fetch_feeds(feeds, limit_per_feed, parse_fn)
    for outcome in outcomes:
        if outcome.error:
            source_repo.record_failure(outcome.source_id)
        else:
            source_repo.record_success(outcome.source_id, now)

    article_repo = RawArticleRepository(session)
    existing = article_repo.existing_urls([a.url for a in fetched if a.url])
    new_articles = [a for a in fetched if a.url and a.url not in existing]

    kept: list[Article] = []
    for article in new_articles:
        score_article(article, persona, now, learning)
        if article.scores["total"] >= threshold:
            kept.append(article)

    source_by_name = {s.name: s.id for s in sources}
    article_ids_by_url: dict[str, object] = {}
    for article in kept:
        row = article_repo.save_scored(article, source_id=source_by_name.get(article.source))
        article_ids_by_url[article.url] = row.id

    cluster_repo = StoryClusterRepository(session)
    opportunity_repo = OpportunityRepository(session)
    clusters = cluster_articles(kept, persona)
    for cluster in clusters:
        row = cluster_repo.create_from_cluster_result(cluster, article_ids_by_url)
        for opp in detect_opportunities(cluster):
            opportunity_repo.create(row.id, opp["type"], opp["label"])

    return DiscoveryResult(fetched=len(fetched), new=len(new_articles), kept=len(kept),
                           clusters=len(clusters), feed_outcomes=outcomes)


def run_discovery_in_background(session_factory: Callable[[], Session]) -> None:
    """Entry point for the "Fetch latest" dashboard button (and, in principle,
    any out-of-request trigger). Discovery takes ~60-90s (17 RSS fetches) —
    too long to hold an HTTP request open, so this runs via FastAPI's
    BackgroundTasks after the response has already been sent, with real status
    tracked in system_config so the frontend can poll instead of guessing.

    Opens its OWN session (session_factory, i.e. SessionLocal) rather than
    reusing the request's session — the request-scoped session is closed the
    moment the response is sent, before this function ever runs.
    """
    from datetime import datetime, timezone

    from app.repositories.system_config import SystemConfigRepository

    session = session_factory()
    cfg = SystemConfigRepository(session)
    try:
        cfg.set("discovery_status", "running", updated_by="dashboard")
        cfg.set("discovery_started_at", datetime.now(timezone.utc).isoformat(), updated_by="dashboard")
        session.commit()

        result = run_discovery_cycle(session)

        cfg.set("discovery_status", "idle", updated_by="dashboard")
        cfg.set("discovery_completed_at", datetime.now(timezone.utc).isoformat(), updated_by="dashboard")
        cfg.set("discovery_last_result", {"fetched": result.fetched, "new": result.new,
                                          "kept": result.kept, "clusters": result.clusters},
               updated_by="dashboard")
        cfg.set("discovery_error", None, updated_by="dashboard")
        session.commit()
    except Exception as e:  # noqa: BLE001 — must still record failure and release the session
        session.rollback()
        cfg.set("discovery_status", "error", updated_by="dashboard")
        cfg.set("discovery_error", str(e)[:500], updated_by="dashboard")
        session.commit()
    finally:
        session.close()
