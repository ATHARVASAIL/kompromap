"""API tests for correlation endpoints (Phase 3)."""
def test_correlation_empty(client, db_session):
    r = client.get("/api/correlation")
    assert r.status_code == 200
    body = r.json()
    assert "total_findings" in body
    assert "asset_risks" in body


def test_correlation_with_findings(client, db_session):
    from app.models import Asset, Edge, Engagement, Finding, Node
    from app.models.edge import EdgeType
    from app.models.enums import NodeType

    eng = Engagement(name="corr-api-test", active=True)
    db_session.add(eng)
    db_session.flush()

    node = Node(node_type=NodeType.ASSET.value, engagement_id=eng.id)
    db_session.add(node)
    db_session.flush()
    asset = Asset(id=node.id, name="app.example.com", asset_type="domain", in_scope=True, tags=["crown-jewel"])
    db_session.add(asset)
    db_session.flush()

    n = Node(node_type=NodeType.FINDING.value, engagement_id=eng.id)
    db_session.add(n)
    db_session.flush()
    f = Finding(id=n.id, title="RCE", cwe="CWE-78", cvss_score=9.5, exploit_public=False, evidence="")
    db_session.add(f)
    db_session.flush()
    db_session.add(Edge(source_node_id=asset.id, target_node_id=f.id, edge_type=EdgeType.HAS_FINDING.value))
    db_session.flush()

    r = client.get("/api/correlation")
    assert r.status_code == 200
    body = r.json()
    assert body["total_findings"] >= 1
    assert len(body["asset_risks"]) >= 1
    assert body["asset_risks"][0]["extended_risk"] > 0
