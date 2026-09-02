#!/usr/bin/env python3
"""Seeds the database from the existing YAML source of truth files:
``profile/persona.yml`` (pillars, interests, full config snapshot),
``profile/facts.yml`` (knowledge items — only ``is_public=True`` ones are ever
citable in generated content, per brief rule 2), and
``automation/sources.yml`` (RSS sources with pre-scored credibility).

Idempotent — safe to re-run after editing any of the three files.

    python scripts/seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from app.db.base import SessionLocal
from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository
from app.repositories.system_config import SystemConfigRepository

ROOT = Path(__file__).resolve().parents[2]
PERSONA_PATH = ROOT / "profile" / "persona.yml"
FACTS_PATH = ROOT / "profile" / "facts.yml"
SOURCES_PATH = ROOT / "automation" / "sources.yml"


def seed_persona(repo: PersonaRepository, persona: dict) -> None:
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key.replace("_", " ").title(),
                           target_share=spec["share"])

    graph, aliases = persona["interest_graph"], persona.get("interest_aliases", {})
    for tier_num, tier_key in ((1, "tier_1"), (2, "tier_2"), (3, "tier_3")):
        for name in graph[tier_key]:
            repo.upsert_interest(name=name, tier=tier_num, aliases=list(aliases.get(name, [])),
                                 pillar=None)

    repo.save_persona_config(version=persona.get("version", "unknown"), config=persona)


def seed_facts(repo: PersonaRepository, facts: dict) -> None:
    """Explodes facts.yml into knowledge_items rows. Everything here is treated as
    is_public=True because facts.yml is, by the project's own rule
    (profile/facts.yml header), already "the only source of truth citable in
    content" — nothing goes in that file that isn't meant to be public.
    """
    repo.clear_knowledge_items()

    identity = facts.get("identity", {})
    if identity:
        repo.add_knowledge_item("bio", identity.get("name_en", "Identity"),
                                yaml.dump(identity, allow_unicode=True), is_public=True,
                                source="profile/facts.yml#identity")

    for item in facts.get("experience", {}).get("items", []):
        repo.add_knowledge_item("project", item.get("role", "Experience"),
                                yaml.dump(item, allow_unicode=True), is_public=True,
                                source="profile/facts.yml#experience")

    for venture in facts.get("ventures", {}).get("items", []):
        repo.add_knowledge_item("company", venture.get("name", "Venture"),
                                yaml.dump(venture, allow_unicode=True), is_public=True,
                                source="profile/facts.yml#ventures")

    for product in facts.get("products_in_development", []):
        repo.add_knowledge_item("product", product.get("name", "Product"),
                                yaml.dump(product, allow_unicode=True), is_public=True,
                                source="profile/facts.yml#products_in_development")

    story = facts.get("story", {})
    if story.get("philosophy"):
        repo.add_knowledge_item("quote", "Management philosophy", story["philosophy"],
                                is_public=True, source="profile/facts.yml#story.philosophy")
    if story.get("current_goal"):
        repo.add_knowledge_item("goal", "Current goal", story["current_goal"],
                                is_public=True, source="profile/facts.yml#story.current_goal")


def seed_sources(repo: SourceRepository, sources: dict) -> None:
    for feed in sources.get("feeds", []):
        repo.upsert(name=feed["name"], url=feed["url"], kind="rss", source_type=feed["type"],
                   credibility=_credibility_for(feed["type"]), region=feed.get("region"))


# Mirrors profile/persona.yml -> source_credibility (kept in sync by hand for now;
# once persona_config is DB-seeded, read this from there instead of duplicating).
_CREDIBILITY = {
    "official_government": 100, "official_company": 95, "major_international_publication": 90,
    "industry_publication": 80, "professional_analyst": 70, "social_media": 55,
    "unknown_website": 20, "unverified_account": 10,
}


def _credibility_for(source_type: str) -> int:
    return _CREDIBILITY.get(source_type, 20)


def main() -> None:
    persona = yaml.safe_load(PERSONA_PATH.read_text(encoding="utf-8"))
    facts = yaml.safe_load(FACTS_PATH.read_text(encoding="utf-8"))
    sources = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))

    session = SessionLocal()
    try:
        persona_repo = PersonaRepository(session)
        seed_persona(persona_repo, persona)
        seed_facts(persona_repo, facts)
        seed_sources(SourceRepository(session), sources)

        cfg_repo = SystemConfigRepository(session)
        cfg_repo.set_auto_publish_green(False, updated_by="seed_script")
        cfg_repo.set("require_approval", True, updated_by="seed_script")
        cfg_repo.set("timezone", "Asia/Riyadh", updated_by="seed_script")
        # launch_date drives the real "auto-publish locked until <date+90d>" display
        # (brief rule 5) — set once, never overwritten by re-seeding.
        if cfg_repo.get("launch_date") is None:
            from datetime import date
            cfg_repo.set("launch_date", date.today().isoformat(), updated_by="seed_script")
        if cfg_repo.get("excluded_topics") is None:
            cfg_repo.set("excluded_topics", [], updated_by="seed_script")

        session.commit()
        print("Seed complete: pillars, interests, persona_config, knowledge_items, sources, system_config.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
