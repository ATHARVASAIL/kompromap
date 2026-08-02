"""Tests for optional API-key auth (app/core/security.py).

Auth is off unless API_KEY is set, so these have to build their own app
instance per-mode rather than reusing the shared `client` fixture —
get_settings() is lru_cached and FastAPI wires the routers at import time.
"""
import importlib

import pytest
from fastapi.testclient import TestClient


def _build_app(monkeypatch, api_key: str | None, debug: str = "false", db_session=None):
    """Rebuild the app with a given API_KEY, clearing the settings cache.

    Takes an optional db_session because a couple of these tests assert on
    a *successful* (200) response from a data route, which needs a working
    database. Without the override they only pass when a real Postgres
    happens to be listening — which made them pass in isolation and fail
    in the full suite. Auth is the subject here, not persistence, so the
    in-memory SQLite session from conftest is exactly right.
    """
    if api_key is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", api_key)
    monkeypatch.setenv("DEBUG", debug)

    from app.core import config

    config.get_settings.cache_clear()

    import app.main

    importlib.reload(app.main)
    app_obj = app.main.app

    if db_session is not None:
        from app.core.db import get_db

        def _override():
            yield db_session

        app_obj.dependency_overrides[get_db] = _override

    return app_obj


@pytest.fixture(autouse=True)
def _restore_settings_cache():
    yield
    from app.core import config

    config.get_settings.cache_clear()
    import app.main

    app.main.app.dependency_overrides.clear()
    importlib.reload(app.main)


def test_no_api_key_configured_leaves_everything_open(monkeypatch, db_session):
    """Default/local mode must behave exactly as it did before auth existed."""
    app = _build_app(monkeypatch, None, db_session=db_session)
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    # Data routes reachable without any header at all.
    assert client.get("/api/graph").status_code == 200


def test_health_stays_open_when_auth_enabled(monkeypatch):
    """Container/LB probes must not need a credential."""
    app = _build_app(monkeypatch, "test-key-123")
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200


def test_data_route_rejects_missing_key(monkeypatch):
    app = _build_app(monkeypatch, "test-key-123")
    client = TestClient(app)
    assert client.get("/api/graph").status_code == 401


def test_data_route_rejects_wrong_key(monkeypatch):
    app = _build_app(monkeypatch, "test-key-123")
    client = TestClient(app)
    assert client.get("/api/graph", headers={"X-API-Key": "nope"}).status_code == 401


def test_data_route_accepts_correct_key(monkeypatch, db_session):
    app = _build_app(monkeypatch, "test-key-123", db_session=db_session)
    client = TestClient(app)
    assert client.get("/api/graph", headers={"X-API-Key": "test-key-123"}).status_code == 200


def test_mutating_route_is_also_protected(monkeypatch):
    """A read-only guard would be useless — writes matter more."""
    app = _build_app(monkeypatch, "test-key-123")
    client = TestClient(app)
    r = client.post("/api/nodes", json={"node_type": "asset", "name": "x", "asset_type": "domain"})
    assert r.status_code == 401


def test_ingest_route_is_protected(monkeypatch):
    app = _build_app(monkeypatch, "test-key-123")
    client = TestClient(app)
    r = client.post("/api/ingest/nmap", files={"file": ("x.xml", b"<nmaprun/>", "application/xml")})
    assert r.status_code == 401


def test_docs_hidden_when_auth_enabled(monkeypatch):
    """The OpenAPI docs advertise the whole API surface; no reason to serve
    them anonymously on a deployment that's otherwise locked down."""
    app = _build_app(monkeypatch, "test-key-123", debug="false")
    client = TestClient(app)
    assert client.get("/docs").status_code == 404


def test_docs_available_locally(monkeypatch):
    app = _build_app(monkeypatch, None)
    client = TestClient(app)
    assert client.get("/docs").status_code == 200
