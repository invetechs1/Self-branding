"""Discovery service tests — network never touched (brief's testing rule).
``parse_fn`` is a fake returning canned feedparser-shaped objects, matching
"RSS ingestion against recorded feed fixtures, not live network in CI".
"""

from datetime import datetime, timezone

import pytest

from app.repositories.clusters import StoryClusterRepository
from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository
from app.services.discovery import FeedSpec, fetch_feeds, run_discovery_cycle


class _FakeParsed:
    def __init__(self, entries):
        self.entries = entries


def _entry(title, summary, url, days_old=0):
    now = datetime.now(timezone.utc)
    published = now.timetuple()
    return {"title": title, "summary": summary, "link": url, "published_parsed": published}


RELEVANT_TITLE = "Saudi PIF backs AI construction monitoring startup with $40 million to expand in Riyadh"
RELEVANT_SUMMARY = "The funding round targets computer vision progress tracking for contractors under Vision 2030."
DUPLICATE_TITLE = "PIF backs AI construction monitoring startup in Riyadh with $40m round"
IRRELEVANT_TITLE = "Local cafe launches new seasonal drink"


def _make_parse_fn(per_feed: dict[str, list], raise_for: set[str] = frozenset()):
    def parse_fn(url):
        if url in raise_for:
            raise RuntimeError("simulated network failure")
        return _FakeParsed(per_feed.get(url, []))
    return parse_fn


def test_fetch_feeds_reads_entries_and_reports_per_feed_outcome():
    feeds = [FeedSpec(source_id=1, name="Feed A", url="https://a.example/rss",
                      source_type="major_international_publication", region="saudi_arabia")]
    parse_fn = _make_parse_fn({
        "https://a.example/rss": [_entry(RELEVANT_TITLE, RELEVANT_SUMMARY, "https://a.example/1")],
    })

    articles, outcomes = fetch_feeds(feeds, parse_fn=parse_fn)

    assert len(articles) == 1
    assert articles[0].title == RELEVANT_TITLE
    assert outcomes[0].count == 1
    assert outcomes[0].error is None


def test_fetch_feeds_one_broken_source_does_not_stop_the_rest():
    feeds = [
        FeedSpec(source_id=1, name="Broken", url="https://broken.example/rss",
                source_type="unknown_website", region="global"),
        FeedSpec(source_id=2, name="Working", url="https://working.example/rss",
                source_type="major_international_publication", region="saudi_arabia"),
    ]
    parse_fn = _make_parse_fn(
        {"https://working.example/rss": [_entry(RELEVANT_TITLE, RELEVANT_SUMMARY, "https://working.example/1")]},
        raise_for={"https://broken.example/rss"},
    )

    articles, outcomes = fetch_feeds(feeds, parse_fn=parse_fn)

    assert len(articles) == 1
    broken_outcome = next(o for o in outcomes if o.name == "Broken")
    assert broken_outcome.error is not None
    assert broken_outcome.count == 0


@pytest.fixture()
def seeded_persona(db_session, persona):
    """Matches what scripts/seed.py actually does before any discovery cycle can
    run: pillars must exist first, since raw_articles.pillar is FK-constrained
    to pillars.key (real data-integrity rule, not a test artifact)."""
    repo = PersonaRepository(db_session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key.replace("_", " ").title(),
                           target_share=spec["share"])
    repo.save_persona_config(version="test", config=persona)
    db_session.flush()
    return persona


def test_discovery_cycle_persists_only_articles_above_threshold(db_session, seeded_persona):
    source_repo = SourceRepository(db_session)
    source_repo.upsert(name="Relevant Source", url="https://relevant.example/rss", kind="rss",
                       source_type="major_international_publication", credibility=90, region="saudi_arabia")
    source_repo.upsert(name="Cafe Blog", url="https://cafe.example/rss", kind="rss",
                       source_type="unknown_website", credibility=20, region="global")
    db_session.flush()

    parse_fn = _make_parse_fn({
        "https://relevant.example/rss": [_entry(RELEVANT_TITLE, RELEVANT_SUMMARY, "https://relevant.example/1")],
        "https://cafe.example/rss": [_entry(IRRELEVANT_TITLE, "A limited edition beverage.",
                                            "https://cafe.example/1")],
    })

    result = run_discovery_cycle(db_session, parse_fn=parse_fn)

    assert result.fetched == 2
    assert result.new == 2
    assert result.kept == 1   # only the Saudi AI+construction story crosses the threshold
    assert result.clusters == 1


def test_discovery_cycle_merges_duplicate_reports_into_one_cluster(db_session, seeded_persona):
    source_repo = SourceRepository(db_session)
    source_repo.upsert(name="Source A", url="https://a.example/rss", kind="rss",
                       source_type="major_international_publication", credibility=90, region="saudi_arabia")
    source_repo.upsert(name="Source B", url="https://b.example/rss", kind="rss",
                       source_type="major_international_publication", credibility=90, region="saudi_arabia")
    db_session.flush()

    parse_fn = _make_parse_fn({
        "https://a.example/rss": [_entry(RELEVANT_TITLE, RELEVANT_SUMMARY, "https://a.example/1")],
        "https://b.example/rss": [_entry(DUPLICATE_TITLE, "Contractors adopt computer vision under Vision 2030.",
                                         "https://b.example/1")],
    })

    result = run_discovery_cycle(db_session, parse_fn=parse_fn)

    assert result.kept == 2
    assert result.clusters == 1   # brief § 15: one event, one cluster

    cluster = StoryClusterRepository(db_session).recent(1)[0]
    assert cluster.source_count == 2


def test_discovery_cycle_skips_already_stored_urls(db_session, seeded_persona):
    source_repo = SourceRepository(db_session)
    source_repo.upsert(name="Relevant Source", url="https://relevant.example/rss", kind="rss",
                       source_type="major_international_publication", credibility=90, region="saudi_arabia")
    db_session.flush()

    parse_fn = _make_parse_fn({
        "https://relevant.example/rss": [_entry(RELEVANT_TITLE, RELEVANT_SUMMARY, "https://relevant.example/1")],
    })

    first = run_discovery_cycle(db_session, parse_fn=parse_fn)
    second = run_discovery_cycle(db_session, parse_fn=parse_fn)

    assert first.kept == 1
    assert second.new == 0
    assert second.kept == 0


def test_discovery_cycle_records_source_failures(db_session, seeded_persona):
    source_repo = SourceRepository(db_session)
    source_repo.upsert(name="Flaky", url="https://flaky.example/rss", kind="rss",
                       source_type="unknown_website", credibility=20, region="global")
    db_session.flush()
    source_id = source_repo.list_enabled()[0].id

    parse_fn = _make_parse_fn({}, raise_for={"https://flaky.example/rss"})

    for _ in range(5):
        run_discovery_cycle(db_session, parse_fn=parse_fn)

    from app.db.models import Source
    refreshed = db_session.get(Source, source_id)
    assert refreshed.failure_count == 5
    assert refreshed.enabled is False


def test_discovery_raises_clear_error_without_seeded_persona(db_session):
    with pytest.raises(RuntimeError, match="seed.py"):
        run_discovery_cycle(db_session, parse_fn=lambda url: _FakeParsed([]))
