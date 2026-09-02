"""Repository for persona/knowledge tables — pillars, interests, knowledge_items,
persona_config. One repository per aggregate, per the brief's repository-pattern
guidance; no business logic here, just typed reads/writes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Interest, KnowledgeItem, PersonaConfig, Pillar


class PersonaRepository:
    def __init__(self, session: Session):
        self.session = session

    # ── pillars ──
    def upsert_pillar(self, key: str, label_ar: str, label_en: str, target_share: float) -> None:
        stmt = pg_insert(Pillar).values(key=key, label_ar=label_ar, label_en=label_en,
                                        target_share=target_share)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Pillar.key],
            set_={"label_ar": label_ar, "label_en": label_en, "target_share": target_share})
        self.session.execute(stmt)

    def list_pillars(self) -> list[Pillar]:
        return list(self.session.scalars(select(Pillar)))

    def get_pillar(self, key: str) -> Pillar | None:
        return self.session.get(Pillar, key)

    def set_pillar_multiplier(self, key: str, multiplier: float) -> None:
        pillar = self.session.get(Pillar, key)
        if pillar is None:
            raise ValueError(f"unknown pillar: {key}")
        pillar.multiplier = multiplier

    def set_pillar_target_share(self, key: str, target_share: float) -> Pillar:
        pillar = self.session.get(Pillar, key)
        if pillar is None:
            raise ValueError(f"unknown pillar: {key}")
        pillar.target_share = target_share
        return pillar

    # ── interests ──
    def upsert_interest(self, name: str, tier: int, aliases: list[str], pillar: str | None) -> Interest:
        existing = self.session.scalar(select(Interest).where(Interest.name == name))
        if existing:
            existing.tier, existing.aliases, existing.pillar = tier, aliases, pillar
            return existing
        row = Interest(name=name, tier=tier, aliases=aliases, pillar=pillar)
        self.session.add(row)
        self.session.flush()
        return row

    def list_interests(self, tier: int | None = None, *, enabled_only: bool = True) -> list[Interest]:
        stmt = select(Interest)
        if enabled_only:
            stmt = stmt.where(Interest.enabled.is_(True))
        if tier is not None:
            stmt = stmt.where(Interest.tier == tier)
        return list(self.session.scalars(stmt))

    def remove_interest(self, interest_id: int) -> None:
        row = self.session.get(Interest, interest_id)
        if row is None:
            raise ValueError(f"unknown interest: {interest_id}")
        self.session.delete(row)

    # ── knowledge items (profile/facts.yml, exploded to rows) ──
    def add_knowledge_item(self, kind: str, title: str, body: str, *, is_public: bool = False,
                           confidence: float = 1.0, source: str | None = None) -> KnowledgeItem:
        item = KnowledgeItem(kind=kind, title=title, body=body, is_public=is_public,
                             confidence=confidence, source=source)
        self.session.add(item)
        self.session.flush()
        return item

    def list_all_knowledge(self) -> list[KnowledgeItem]:
        """Everything, public and private — for the Settings screen. Never use
        this list to feed a content-generation prompt (brief rule 2) — use
        list_public_knowledge for that."""
        return list(self.session.scalars(select(KnowledgeItem).order_by(KnowledgeItem.kind)))

    def get_knowledge_item(self, item_id) -> KnowledgeItem | None:
        return self.session.get(KnowledgeItem, item_id)

    def update_knowledge_item(self, item_id, *, title: str | None = None, body: str | None = None,
                              is_public: bool | None = None) -> KnowledgeItem:
        row = self.get_knowledge_item(item_id)
        if row is None:
            raise ValueError(f"unknown knowledge item: {item_id}")
        if title is not None:
            row.title = title
        if body is not None:
            row.body = body
        if is_public is not None:
            row.is_public = is_public
        return row

    def list_public_knowledge(self) -> list[KnowledgeItem]:
        """Only rows an agent is allowed to cite in published content (brief rule 2)."""
        return list(self.session.scalars(
            select(KnowledgeItem).where(KnowledgeItem.is_public.is_(True))))

    def clear_knowledge_items(self) -> None:
        """Used by the seed script to make re-seeding from facts.yml idempotent."""
        self.session.query(KnowledgeItem).delete()

    # ── persona_config (versioned snapshot of profile/persona.yml) ──
    def save_persona_config(self, version: str, config: dict) -> PersonaConfig:
        self.session.query(PersonaConfig).filter(PersonaConfig.active.is_(True)) \
            .update({"active": False})
        row = PersonaConfig(version=version, config=config, active=True)
        self.session.add(row)
        return row

    def get_active_persona_config(self) -> PersonaConfig | None:
        return self.session.scalar(select(PersonaConfig).where(PersonaConfig.active.is_(True)))
