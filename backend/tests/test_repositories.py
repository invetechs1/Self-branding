"""Integration tests for the repository layer — real Postgres (see conftest's
``db_session`` fixture), not mocks, per the brief's "integration tests for the
database" requirement."""

from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository
from app.repositories.system_config import SystemConfigRepository


def test_pillar_upsert_is_idempotent(db_session):
    repo = PersonaRepository(db_session)
    repo.upsert_pillar("ai_technology", "الذكاء الاصطناعي والتقنية", "AI & Technology", 0.30)
    repo.upsert_pillar("ai_technology", "الذكاء الاصطناعي والتقنية", "AI & Technology", 0.35)

    pillars = repo.list_pillars()
    assert len(pillars) == 1
    assert float(pillars[0].target_share) == 0.35


def test_interest_upsert_and_list_by_tier(db_session):
    repo = PersonaRepository(db_session)
    repo.upsert_pillar("ai_technology", "AI", "AI", 0.3)
    repo.upsert_interest("Artificial Intelligence", tier=1, aliases=["ai", "ml"], pillar="ai_technology")
    repo.upsert_interest("Leadership", tier=3, aliases=[], pillar=None)

    tier1 = repo.list_interests(tier=1)
    assert len(tier1) == 1
    assert tier1[0].name == "Artificial Intelligence"
    assert "ai" in tier1[0].aliases


def test_knowledge_items_public_flag_filters_correctly(db_session):
    repo = PersonaRepository(db_session)
    repo.add_knowledge_item("company", "Azoom United Contracting", "founder and CEO",
                            is_public=True, source="facts.yml")
    repo.add_knowledge_item("opinion", "unreviewed draft opinion", "not yet cleared",
                            is_public=False)

    public = repo.list_public_knowledge()
    assert len(public) == 1
    assert public[0].title == "Azoom United Contracting"


def test_source_upsert_deduplicates_by_url(db_session):
    repo = SourceRepository(db_session)
    repo.upsert(name="Arab News", url="https://arabnews.com/rss.xml", kind="rss",
               source_type="major_international_publication", credibility=90, region="saudi_arabia")
    repo.upsert(name="Arab News — Business", url="https://arabnews.com/rss.xml", kind="rss",
               source_type="major_international_publication", credibility=90, region="saudi_arabia")

    sources = repo.list_enabled()
    assert len(sources) == 1
    assert sources[0].name == "Arab News — Business"


def test_source_auto_disables_after_five_failures(db_session):
    repo = SourceRepository(db_session)
    repo.upsert(name="Flaky Feed", url="https://flaky.example/rss", kind="rss",
               source_type="unknown_website", credibility=20, region="global")
    source = repo.list_enabled()[0]

    for _ in range(5):
        repo.record_failure(source.id)

    assert source.enabled is False


def test_auto_publish_green_is_seeded_false_by_the_migration_itself(db_session):
    """0001_init.sql seeds this row directly (brief rule 5) — it must already be
    False before any application code runs, not just after a repository call."""
    repo = SystemConfigRepository(db_session)
    assert repo.get("auto_publish_green") is False


def test_auto_publish_green_can_be_explicitly_updated(db_session):
    repo = SystemConfigRepository(db_session)
    repo.set_auto_publish_green(True, updated_by="test")
    assert repo.get("auto_publish_green") is True
    repo.set_auto_publish_green(False, updated_by="test")
    assert repo.get("auto_publish_green") is False
