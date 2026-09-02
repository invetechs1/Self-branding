"""API layer tests — TestClient against the real FastAPI app, DB dependency
overridden to the test session so each test stays isolated and rolled back."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import settings
from app.db.base import get_session
from app.repositories.sources import SourceRepository


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_requires_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_sources_endpoint_requires_api_key(client):
    resp = client.get("/sources")
    assert resp.status_code == 401


def test_sources_endpoint_rejects_wrong_key(client):
    resp = client.get("/sources", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_sources_endpoint_returns_seeded_sources(client, db_session):
    SourceRepository(db_session).upsert(
        name="Arab News", url="https://arabnews.com/rss.xml", kind="rss",
        source_type="major_international_publication", credibility=90, region="saudi_arabia")

    resp = client.get("/sources", headers={"X-API-Key": settings.api_key})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Arab News"
    assert body[0]["credibility"] == 90


def test_system_config_endpoint_returns_safety_defaults(client, db_session):
    from app.repositories.system_config import SystemConfigRepository
    SystemConfigRepository(db_session).set_auto_publish_green(False, updated_by="test")

    resp = client.get("/system-config", headers={"X-API-Key": settings.api_key})
    assert resp.status_code == 200
    assert resp.json()["auto_publish_green"] is False
