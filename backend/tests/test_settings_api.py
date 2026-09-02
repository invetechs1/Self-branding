"""Settings screen API tests — every value must trace to a real row, so each
test seeds real data and asserts the exact value comes back, not a shape check."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import settings as app_settings
from app.db.base import get_session
from app.repositories.persona import PersonaRepository
from app.repositories.sources import SourceRepository
from app.repositories.system_config import SystemConfigRepository

HEADERS = {"X-API-Key": app_settings.api_key}


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_persona(db_session, persona):
    repo = PersonaRepository(db_session)
    for key, spec in persona["content_pillars"].items():
        repo.upsert_pillar(key=key, label_ar=spec["label_ar"], label_en=key, target_share=spec["share"])
    repo.save_persona_config(version="test", config=persona)
    db_session.flush()


def test_profile_reflects_real_identity_and_connection_status(client, db_session, persona, monkeypatch):
    # Force deterministic credential state — this machine's real backend/.env may
    # or may not have X/LinkedIn keys configured, and the test must not depend on
    # that ambient state either way.
    monkeypatch.setattr(app_settings, "x_api_key", "")
    monkeypatch.setattr(app_settings, "linkedin_access_token", "")
    _seed_persona(db_session, persona)
    resp = client.get("/settings/profile", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name_ar"] == persona["identity"]["name_ar"]
    assert body["name_en"] == persona["identity"]["name_en"]
    assert body["accounts"]["x"]["connected"] is False
    assert body["accounts"]["instagram"]["note"] == "on hold"


def test_profile_reports_connected_when_credentials_are_configured(client, db_session, persona, monkeypatch):
    monkeypatch.setattr(app_settings, "x_api_key", "some-real-key")
    _seed_persona(db_session, persona)
    resp = client.get("/settings/profile", headers=HEADERS)
    assert resp.json()["accounts"]["x"]["connected"] is True


def test_profile_without_persona_seeded_returns_503(client):
    resp = client.get("/settings/profile", headers=HEADERS)
    assert resp.status_code == 503


def test_knowledge_crud(client, db_session, persona):
    _seed_persona(db_session, persona)
    create = client.post("/settings/knowledge", headers=HEADERS,
                         json={"kind": "opinion", "title": "Test opinion", "body": "Body text",
                              "is_public": False})
    assert create.status_code == 200
    item_id = create.json()["id"]

    listed = client.get("/settings/knowledge", headers=HEADERS).json()
    assert any(i["id"] == item_id for i in listed)

    updated = client.patch(f"/settings/knowledge/{item_id}", headers=HEADERS,
                           json={"is_public": True, "body": "Updated body"})
    assert updated.status_code == 200
    assert updated.json()["is_public"] is True
    assert updated.json()["body"] == "Updated body"


def test_knowledge_update_unknown_id_returns_404(client, db_session, persona):
    _seed_persona(db_session, persona)
    import uuid
    resp = client.patch(f"/settings/knowledge/{uuid.uuid4()}", headers=HEADERS, json={"title": "x"})
    assert resp.status_code == 404


def test_pillars_reflect_real_target_share_and_multiplier(client, db_session, persona):
    _seed_persona(db_session, persona)
    listed = client.get("/settings/pillars", headers=HEADERS).json()
    assert len(listed) == len(persona["content_pillars"])
    ai = next(p for p in listed if p["key"] == "ai_technology")
    assert ai["target_share"] == persona["content_pillars"]["ai_technology"]["share"]
    assert ai["multiplier"] == 1.0  # neutral until the learning engine runs


def test_pillar_target_share_can_be_updated(client, db_session, persona):
    _seed_persona(db_session, persona)
    resp = client.patch("/settings/pillars/ai_technology", headers=HEADERS, json={"target_share": 0.35})
    assert resp.status_code == 200
    assert resp.json()["target_share"] == 0.35


def test_pillar_target_share_rejects_out_of_range(client, db_session, persona):
    _seed_persona(db_session, persona)
    resp = client.patch("/settings/pillars/ai_technology", headers=HEADERS, json={"target_share": 1.5})
    assert resp.status_code == 400


def test_topics_add_and_remove(client, db_session, persona):
    _seed_persona(db_session, persona)
    created = client.post("/settings/topics", headers=HEADERS,
                          json={"name": "Green Building", "tier": 3})
    assert created.status_code == 200
    topic_id = created.json()["id"]

    listed = client.get("/settings/topics", headers=HEADERS).json()
    assert any(t["name"] == "Green Building" for t in listed["tracked"])
    assert listed["excluded"] == []

    removed = client.delete(f"/settings/topics/{topic_id}", headers=HEADERS)
    assert removed.status_code == 200


def test_excluded_topics_add_and_remove(client, db_session, persona):
    _seed_persona(db_session, persona)
    added = client.post("/settings/topics/excluded", headers=HEADERS, json={"topic": "Politics"})
    assert added.status_code == 200
    assert "Politics" in added.json()

    listed = client.get("/settings/topics", headers=HEADERS).json()
    assert "Politics" in listed["excluded"]

    removed = client.delete("/settings/topics/excluded/Politics", headers=HEADERS)
    assert removed.status_code == 200
    assert "Politics" not in removed.json()

    listed_after = client.get("/settings/topics", headers=HEADERS).json()
    assert not any(t["id"] == topic_id for t in listed_after["tracked"])


def test_sources_list_and_toggle(client, db_session, persona):
    _seed_persona(db_session, persona)
    SourceRepository(db_session).upsert(name="Test Source", url="https://example.test/rss", kind="rss",
                                        source_type="industry_publication", credibility=80, region="global")
    db_session.flush()

    listed = client.get("/settings/sources", headers=HEADERS).json()
    assert len(listed) == 1
    assert listed[0]["enabled"] is True

    toggled = client.post(f"/settings/sources/{listed[0]['id']}/toggle", headers=HEADERS)
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is False


def test_publishing_rules_locked_within_first_90_days(client, db_session, persona):
    _seed_persona(db_session, persona)
    from datetime import date
    SystemConfigRepository(db_session).set("launch_date", date.today().isoformat(), updated_by="test")
    SystemConfigRepository(db_session).set_auto_publish_green(False, updated_by="test")
    db_session.flush()

    resp = client.get("/settings/publishing", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["manual_period_locked"] is True
    assert body["auto_publish_green"] is False


def test_approval_thresholds_come_from_persona_config(client, db_session, persona):
    _seed_persona(db_session, persona)
    resp = client.get("/settings/approval-thresholds", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["pipeline_entry"] == persona["thresholds"]["pipeline_entry"]


def test_safety_config_comes_from_persona_config(client, db_session, persona):
    _seed_persona(db_session, persona)
    resp = client.get("/settings/safety", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["red_flag_terms"] == persona["safety"]["red_flag_terms"]


def test_system_config_reflects_real_values(client, db_session, persona):
    _seed_persona(db_session, persona)
    SystemConfigRepository(db_session).set("timezone", "Asia/Riyadh", updated_by="test")
    db_session.flush()
    resp = client.get("/settings/system", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Asia/Riyadh"
    assert resp.json()["default_language"] == persona["voice"]["default_language"]


def test_settings_endpoints_require_auth(client):
    assert client.get("/settings/profile").status_code == 401
    assert client.get("/settings/pillars").status_code == 401
