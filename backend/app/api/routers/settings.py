"""Settings endpoints (brief § 12 / architecture-assessment.md § F "Settings").
Every value shown is read from real tables — no placeholder/demo data. A
field with nothing on file (e.g. city) is returned empty/null and the
frontend says so plainly, rather than this API inventing a value.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.config import settings as app_settings
from app.db.base import get_session
from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository
from app.repositories.system_config import SystemConfigRepository

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_api_key)])

MANUAL_APPROVAL_PERIOD_DAYS = 90   # brief rule 5 — first 3 months, non-negotiable


def _persona(session: Session) -> dict:
    cfg = PersonaRepository(session).get_active_persona_config()
    if cfg is None:
        raise HTTPException(status_code=503, detail="persona not seeded — run scripts/seed.py")
    return cfg.config


# ── Profile ──

class ProfileOut(BaseModel):
    name_ar: str
    name_en: str
    headline: str | None
    city: str | None
    accounts: dict


@router.get("/profile", response_model=ProfileOut)
def get_profile(session: Session = Depends(get_session)) -> ProfileOut:
    persona = _persona(session)
    identity = persona.get("identity", {})
    return ProfileOut(
        name_ar=identity.get("name_ar", ""), name_en=identity.get("name_en", ""),
        headline=identity.get("professional_identity") or identity.get("positioning"),
        city=identity.get("city"),
        accounts={
            "x": {"connected": bool(app_settings.x_api_key), "note": "@alsalamah_y" if app_settings.x_api_key else None},
            "linkedin": {"connected": bool(app_settings.linkedin_access_token)},
            "instagram": {"connected": bool(app_settings.instagram_access_token), "note": "on hold"},
        },
    )


# ── Knowledge / Facts ──

class KnowledgeOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    is_public: bool
    source: str | None

    model_config = {"from_attributes": True}


class KnowledgeCreate(BaseModel):
    kind: str
    title: str
    body: str
    is_public: bool = True


class KnowledgeUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    is_public: bool | None = None


@router.get("/knowledge", response_model=list[KnowledgeOut])
def list_knowledge(session: Session = Depends(get_session)) -> list[KnowledgeOut]:
    return list(PersonaRepository(session).list_all_knowledge())


@router.post("/knowledge", response_model=KnowledgeOut)
def add_knowledge(body: KnowledgeCreate, session: Session = Depends(get_session)) -> KnowledgeOut:
    item = PersonaRepository(session).add_knowledge_item(
        body.kind, body.title, body.body, is_public=body.is_public, source="settings-ui")
    session.commit()
    return item


@router.patch("/knowledge/{item_id}", response_model=KnowledgeOut)
def update_knowledge(item_id: uuid.UUID, body: KnowledgeUpdate,
                     session: Session = Depends(get_session)) -> KnowledgeOut:
    try:
        item = PersonaRepository(session).update_knowledge_item(
            item_id, title=body.title, body=body.body, is_public=body.is_public)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    session.commit()
    return item


# ── Content Pillars ──

class PillarOut(BaseModel):
    key: str
    label_ar: str
    label_en: str
    target_share: float
    multiplier: float

    model_config = {"from_attributes": True}


class PillarUpdate(BaseModel):
    target_share: float


@router.get("/pillars", response_model=list[PillarOut])
def list_pillars(session: Session = Depends(get_session)) -> list[PillarOut]:
    rows = PersonaRepository(session).list_pillars()
    return [PillarOut(key=p.key, label_ar=p.label_ar, label_en=p.label_en,
                      target_share=float(p.target_share), multiplier=float(p.multiplier)) for p in rows]


@router.patch("/pillars/{key}", response_model=PillarOut)
def update_pillar(key: str, body: PillarUpdate, session: Session = Depends(get_session)) -> PillarOut:
    if not (0 <= body.target_share <= 1):
        raise HTTPException(status_code=400, detail="target_share must be between 0 and 1")
    try:
        p = PersonaRepository(session).set_pillar_target_share(key, body.target_share)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    session.commit()
    return PillarOut(key=p.key, label_ar=p.label_ar, label_en=p.label_en,
                     target_share=float(p.target_share), multiplier=float(p.multiplier))


# ── Topics (interests) ──

class InterestOut(BaseModel):
    id: int
    name: str
    tier: int
    aliases: list[str]
    pillar: str | None

    model_config = {"from_attributes": True}


class TopicsOut(BaseModel):
    tracked: list[InterestOut]
    excluded: list[str]


class InterestCreate(BaseModel):
    name: str
    tier: int = 3
    pillar: str | None = None


@router.get("/topics", response_model=TopicsOut)
def get_topics(session: Session = Depends(get_session)) -> TopicsOut:
    persona_repo = PersonaRepository(session)
    tracked = persona_repo.list_interests(enabled_only=False)
    excluded = SystemConfigRepository(session).get("excluded_topics", [])
    return TopicsOut(tracked=list(tracked), excluded=excluded)


@router.post("/topics", response_model=InterestOut)
def add_topic(body: InterestCreate, session: Session = Depends(get_session)) -> InterestOut:
    row = PersonaRepository(session).upsert_interest(body.name, body.tier, [], body.pillar)
    session.commit()
    return row


@router.delete("/topics/{interest_id}")
def remove_topic(interest_id: int, session: Session = Depends(get_session)) -> dict:
    try:
        PersonaRepository(session).remove_interest(interest_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    session.commit()
    return {"id": interest_id, "removed": True}


class ExcludedTopicIn(BaseModel):
    topic: str


@router.post("/topics/excluded", response_model=list[str])
def add_excluded_topic(body: ExcludedTopicIn, session: Session = Depends(get_session)) -> list[str]:
    cfg = SystemConfigRepository(session)
    current = cfg.get("excluded_topics", [])
    if body.topic not in current:
        current = [*current, body.topic]
        cfg.set("excluded_topics", current, updated_by="settings-ui")
        session.commit()
    return current


@router.delete("/topics/excluded/{topic}", response_model=list[str])
def remove_excluded_topic(topic: str, session: Session = Depends(get_session)) -> list[str]:
    cfg = SystemConfigRepository(session)
    current = [t for t in cfg.get("excluded_topics", []) if t != topic]
    cfg.set("excluded_topics", current, updated_by="settings-ui")
    session.commit()
    return current


# ── Sources ──

class SourceOut(BaseModel):
    id: int
    name: str
    url: str
    source_type: str
    credibility: int
    region: str | None
    enabled: bool
    last_fetched_at: datetime | None
    failure_count: int

    model_config = {"from_attributes": True}


@router.get("/sources", response_model=list[SourceOut])
def list_all_sources(session: Session = Depends(get_session)) -> list[SourceOut]:
    return list(SourceRepository(session).list_all())


@router.post("/sources/{source_id}/toggle", response_model=SourceOut)
def toggle_source(source_id: int, session: Session = Depends(get_session)) -> SourceOut:
    repo = SourceRepository(session)
    existing = next((s for s in repo.list_all() if s.id == source_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"unknown source: {source_id}")
    row = repo.set_enabled(source_id, not existing.enabled)
    session.commit()
    return row


# ── Publishing rules ──

class PublishingRulesOut(BaseModel):
    auto_publish_green: bool
    require_approval: bool
    manual_period_locked: bool
    manual_period_ends: str


@router.get("/publishing", response_model=PublishingRulesOut)
def get_publishing_rules(session: Session = Depends(get_session)) -> PublishingRulesOut:
    cfg = SystemConfigRepository(session)
    launch = cfg.get("launch_date")
    launch_date = date.fromisoformat(launch) if launch else date.today()
    ends = launch_date + timedelta(days=MANUAL_APPROVAL_PERIOD_DAYS)
    return PublishingRulesOut(
        auto_publish_green=bool(cfg.get("auto_publish_green", False)),
        require_approval=bool(cfg.get("require_approval", True)),
        manual_period_locked=date.today() < ends,
        manual_period_ends=ends.isoformat(),
    )


# ── Approval thresholds (read-only — sourced from persona_config) ──

@router.get("/approval-thresholds")
def get_approval_thresholds(session: Session = Depends(get_session)) -> dict:
    return _persona(session).get("thresholds", {})


# ── Safety configuration (read-only — sourced from persona_config) ──

@router.get("/safety")
def get_safety_config(session: Session = Depends(get_session)) -> dict:
    return _persona(session).get("safety", {})


# ── System configuration ──

@router.get("/system")
def get_system_config(session: Session = Depends(get_session)) -> dict:
    persona = _persona(session)
    cfg = SystemConfigRepository(session)
    return {
        "timezone": cfg.get("timezone", "Asia/Riyadh"),
        "default_language": persona.get("voice", {}).get("default_language", "ar"),
        "discovery_cadence": "Every 3 hours",  # docs/technical-requirements.md § 7
        "environment": app_settings.environment,
    }
