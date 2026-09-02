"""Login endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import settings
from app.db.base import get_session
from app.repositories.users import UserRepository

HEADERS = {"X-API-Key": settings.api_key}


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_login_requires_api_key(client):
    resp = client.post("/auth/login", json={"email": "yahya@bassir.net", "password": "x"})
    assert resp.status_code == 401


def test_login_succeeds_with_correct_credentials(client, db_session):
    UserRepository(db_session).create_or_update("yahya@bassir.net", "Bassir@20302030")
    resp = client.post("/auth/login", json={"email": "yahya@bassir.net", "password": "Bassir@20302030"},
                       headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["email"] == "yahya@bassir.net"


def test_login_fails_with_wrong_password(client, db_session):
    UserRepository(db_session).create_or_update("yahya@bassir.net", "Bassir@20302030")
    resp = client.post("/auth/login", json={"email": "yahya@bassir.net", "password": "wrong"},
                       headers=HEADERS)
    assert resp.status_code == 401


def test_login_fails_for_unknown_user(client):
    resp = client.post("/auth/login", json={"email": "nobody@bassir.net", "password": "x"},
                       headers=HEADERS)
    assert resp.status_code == 401
