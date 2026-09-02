"""API tests for /discover/*. The actual background execution is tested in
test_discovery_background.py against an isolated session — here we only
verify the HTTP contract, with the background function stubbed out so a test
request never touches the real app.db.base.SessionLocal (which is bound to
whatever DATABASE_URL happens to be configured in the ambient environment,
not this test's disposable container)."""

import pytest
from fastapi.testclient import TestClient

import app.api.routers.discovery as discovery_router
from app.api.main import app
from app.config import settings as app_settings
from app.db.base import get_session
from app.repositories.system_config import SystemConfigRepository

HEADERS = {"X-API-Key": app_settings.api_key}


@pytest.fixture()
def client(db_session, monkeypatch):
    app.dependency_overrides[get_session] = lambda: db_session
    # Never let a test request schedule a background task against the real
    # SessionLocal/DATABASE_URL — only test the HTTP contract here.
    monkeypatch.setattr(discovery_router, "run_discovery_in_background", lambda session_factory: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_status_requires_auth(client):
    assert client.get("/discover/status").status_code == 401


def test_status_defaults_to_idle(client):
    resp = client.get("/discover/status", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"


def test_trigger_returns_202_and_running_status(client):
    resp = client.post("/discover/run", headers=HEADERS)
    assert resp.status_code == 202
    assert resp.json()["status"] == "running"


def test_trigger_rejects_when_already_running(client, db_session):
    SystemConfigRepository(db_session).set("discovery_status", "running", updated_by="test")
    db_session.flush()
    resp = client.post("/discover/run", headers=HEADERS)
    assert resp.status_code == 409


def test_status_reflects_last_result(client, db_session):
    SystemConfigRepository(db_session).set(
        "discovery_last_result", {"fetched": 100, "new": 20, "kept": 5, "clusters": 5}, updated_by="test")
    SystemConfigRepository(db_session).set("discovery_status", "idle", updated_by="test")
    db_session.flush()
    resp = client.get("/discover/status", headers=HEADERS)
    assert resp.json()["last_result"]["kept"] == 5
