"""Tests for the "Fetch latest" background trigger — status transitions must
be real and correct, since the dashboard button polls them instead of holding
the HTTP request open for the ~60-90s a full cycle takes."""

from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository
from app.repositories.system_config import SystemConfigRepository
from app.services.discovery import run_discovery_in_background


def _seed(session, persona):
    repo = PersonaRepository(session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key, target_share=spec["share"])
    repo.save_persona_config(version="test", config=persona)
    SourceRepository(session).upsert(name="Test Source", url="https://example.test/rss", kind="rss",
                                     source_type="industry_publication", credibility=80, region="global")
    session.flush()


class _EmptyFeedParseResult:
    """Matches real feedparser output's dual attribute/dict access — fetch_feeds
    falls back to `.get("entries")` when `.entries` is empty, exactly as it
    would for a genuinely empty real RSS feed."""
    entries = []

    def get(self, key, default=None):
        return getattr(self, key, default)


def _empty_parse_fn(url):
    return _EmptyFeedParseResult()


def test_background_run_sets_idle_status_and_result_on_success(bg_session_factory, persona):
    session = bg_session_factory()
    _seed(session, persona)
    session.commit()

    import app.services.discovery as discovery_module
    original = discovery_module.fetch_feeds

    def patched_fetch_feeds(feeds, limit_per_feed=25, parse_fn=None):
        return original(feeds, limit_per_feed, _empty_parse_fn)
    discovery_module.fetch_feeds = patched_fetch_feeds
    try:
        run_discovery_in_background(bg_session_factory)
    finally:
        discovery_module.fetch_feeds = original

    cfg = SystemConfigRepository(session)
    assert cfg.get("discovery_status") == "idle"
    assert cfg.get("discovery_completed_at") is not None
    assert cfg.get("discovery_last_result") == {"fetched": 0, "new": 0, "kept": 0, "clusters": 0}
    assert cfg.get("discovery_error") is None


def test_background_run_sets_error_status_on_failure(bg_session_factory):
    # No persona_config seeded -> run_discovery_cycle raises immediately
    run_discovery_in_background(bg_session_factory)

    session = bg_session_factory()
    cfg = SystemConfigRepository(session)
    assert cfg.get("discovery_status") == "error"
    assert "seed.py" in (cfg.get("discovery_error") or "")


def test_background_run_transitions_through_running_state(bg_session_factory, persona, monkeypatch):
    session = bg_session_factory()
    _seed(session, persona)
    session.commit()

    seen_statuses = []
    original_set = SystemConfigRepository.set

    def spy_set(self, key, value, updated_by):
        if key == "discovery_status":
            seen_statuses.append(value)
        return original_set(self, key, value, updated_by)
    monkeypatch.setattr(SystemConfigRepository, "set", spy_set)

    import app.services.discovery as discovery_module
    original = discovery_module.fetch_feeds
    discovery_module.fetch_feeds = lambda feeds, limit_per_feed=25, parse_fn=None: original(feeds, limit_per_feed, _empty_parse_fn)
    try:
        run_discovery_in_background(bg_session_factory)
    finally:
        discovery_module.fetch_feeds = original

    assert seen_statuses == ["running", "idle"]
