"""API tests for dedup endpoints (Phase 2)."""
import uuid

from app.models import Asset, Edge, Engagement, Finding, Node
from app.models.edge import EdgeType
from app.models.enums import NodeType


def _setup(db, name="api-dedup-test"):
    eng = Engagement(name=name, active=True)
    db.add(eng)
    db.flush()
    node = Node(node_type=NodeType.ASSET.value, engagement_id=eng.id)
    db.add(node)
    db.flush()
    asset = Asset(id=node.id, name=f"{name}.com", asset_type="domain", in_scope=True, tags=[])
    db.add(asset)
    db.flush()
    return eng, asset


def _make_finding(db, eng_id, asset, title):
    n = Node(node_type=NodeType.FINDING.value, engagement_id=eng_id)
    db.add(n)
    db.flush()
    f = Finding(id=n.id, title=title, cwe="CWE-79", cvss_score=5.0, exploit_public=False, evidence="")
    db.add(f)
    db.flush()
    db.add(Edge(source_node_id=asset.id, target_node_id=f.id, edge_type=EdgeType.HAS_FINDING.value))
    db.flush()
    return f


def test_run_dedup_scan(client, db_session):
    eng, asset = _setup(db_session)
    _make_finding(db_session, eng.id, asset, "XSS /search")
    _make_finding(db_session, eng.id, asset, "XSS /search")

    r = client.post("/api/dedup/scan", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "scan" in body


def test_list_candidates_empty(client, db_session):
    eng, _ = _setup(db_session, "api-cand-empty")
    r = client.get("/api/dedup/candidates")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_latest_scan_none(client, db_session):
    eng, _ = _setup(db_session, "api-no-scan")
    r = client.get("/api/dedup/scan/latest")
    assert r.status_code == 200, r.text
    assert r.json() is None
