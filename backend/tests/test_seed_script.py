"""End-to-end test of scripts/seed.py against a real database — proves the
existing profile/persona.yml, profile/facts.yml, and automation/sources.yml
files actually load without error and produce sane data, closing the loop
architecture-assessment.md's reuse map promised."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import seed as seed_script  # noqa: E402

from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository
from app.repositories.system_config import SystemConfigRepository


def test_seed_script_populates_all_tables(db_session):
    persona = seed_script.yaml.safe_load(seed_script.PERSONA_PATH.read_text(encoding="utf-8"))
    facts = seed_script.yaml.safe_load(seed_script.FACTS_PATH.read_text(encoding="utf-8"))
    sources = seed_script.yaml.safe_load(seed_script.SOURCES_PATH.read_text(encoding="utf-8"))

    persona_repo = PersonaRepository(db_session)
    seed_script.seed_persona(persona_repo, persona)
    seed_script.seed_facts(persona_repo, facts)
    seed_script.seed_sources(SourceRepository(db_session), sources)

    cfg_repo = SystemConfigRepository(db_session)
    cfg_repo.set_auto_publish_green(False, updated_by="test")

    assert len(persona_repo.list_pillars()) == len(persona["content_pillars"])
    assert len(persona_repo.list_interests()) > 0
    assert len(persona_repo.list_public_knowledge()) > 0  # facts.yml always has ventures/experience
    assert persona_repo.get_active_persona_config() is not None
    assert len(SourceRepository(db_session).list_enabled()) == len(sources["feeds"])
    assert cfg_repo.get("auto_publish_green") is False


def test_seed_is_idempotent(db_session):
    """Re-running the seed (e.g. after editing facts.yml) must not duplicate rows."""
    persona = seed_script.yaml.safe_load(seed_script.PERSONA_PATH.read_text(encoding="utf-8"))
    facts = seed_script.yaml.safe_load(seed_script.FACTS_PATH.read_text(encoding="utf-8"))

    repo = PersonaRepository(db_session)
    seed_script.seed_persona(repo, persona)
    seed_script.seed_facts(repo, facts)
    first_pillar_count = len(repo.list_pillars())
    first_knowledge_count = len(repo.list_public_knowledge())

    seed_script.seed_persona(repo, persona)
    seed_script.seed_facts(repo, facts)

    assert len(repo.list_pillars()) == first_pillar_count
    assert len(repo.list_public_knowledge()) == first_knowledge_count
