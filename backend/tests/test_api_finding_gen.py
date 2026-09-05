"""API tests for the finding generation endpoints."""
import uuid

import pytest

from app.models import Asset, Edge, EdgeType, Finding, NodeType


def _finding(db_session, title="test finding", **kw):
    f = Finding(
        id=uuid.uuid4(),
        node_type=NodeType.FINDING.value,
        title=title,
        status="open",
        **kw,
    )
    db_session.add(f)
    db_session.flush()
    return f


def _asset(db_session, name="asset", **kw):
    a = Asset(
        id=uuid.uuid4(),
        node_type=NodeType.ASSET.value,
        name=name,
        asset_type="domain",
        **kw,
    )
    db_session.add(a)
    db_session.flush()
    return a


def _edge(db_session, source, target, edge_type, weight=None):
    e = Edge(
        id=uuid.uuid4(),
        source_node_id=source.id,
        target_node_id=target.id,
        edge_type=edge_type.value,
        weight=weight,
    )
    db_session.add(e)
    db_session.flush()
    return e


class TestFindingGenStatus:
    def test_returns_status(self, client):
        """Status endpoint returns JSON with available/provider."""
        resp = client.get("/api/finding-gen/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "provider" in data


class TestFindingGenGenerate:
    def test_generates_for_valid_finding(self, client, db_session):
        finding = _finding(db_session)
        asset = _asset(db_session)
        _edge(db_session, finding, asset, EdgeType.YIELDS)
        db_session.commit()

        # No AI provider in test env → 503, not 500
        resp = client.post(
            "/api/finding-gen/generate",
            json={"finding_id": str(finding.id)},
        )
        assert resp.status_code in (200, 503)

    def test_requires_finding_id(self, client):
        resp = client.post("/api/finding-gen/generate", json={})
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client):
        resp = client.post(
            "/api/finding-gen/generate",
            json={"finding_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404
