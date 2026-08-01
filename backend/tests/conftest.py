"""Shared test fixtures.

Uses an in-memory SQLite DB rather than Postgres. This works because the
model layer uses cross-dialect types (sqlalchemy.Uuid, JSON-with-Postgres-
variant) specifically so it's exercisable without a live Postgres — see the
comments in app/models/node.py and app/models/edge.py. Production always
runs against Postgres per the fixed stack; this is a test-only convenience.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers every table on Base.metadata; see below
from app.core.db import Base

# Without this import, Base.metadata only has tables for whichever model
# modules some other test file happened to import first — fine by luck most
# of the time, but a real bug for any test file that only touches the API
# through the `client` fixture and never imports app.models directly.


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session: Session):
    from fastapi.testclient import TestClient

    from app.core.db import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def engagement_id(db_session: Session):
    """A ready-to-use engagement id for tests that call service-layer
    functions (e.g. ingest_parse_result) directly, bypassing the API layer
    that would otherwise resolve the active engagement automatically."""
    from app.services.engagements import get_active_engagement

    return get_active_engagement(db_session).id
