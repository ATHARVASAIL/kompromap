def _create(client, node_type, **fields):
    r = client.post("/api/nodes", json={"node_type": node_type, **fields})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _edge(client, source_id, target_id, edge_type):
    r = client.post(
        "/api/edges",
        json={"source_node_id": source_id, "target_node_id": target_id, "edge_type": edge_type},
    )
    assert r.status_code == 201, r.text


def test_dashboard_empty_engagement(client):
    engagement = client.get("/api/engagements/active").json()
    r = client.get(f"/api/engagements/{engagement['id']}/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_nodes"] == 0
    assert body["total_edges"] == 0
    assert body["entry_point_count"] == 0
    assert body["crown_jewel_count"] == 0
    assert body["paths_to_crown_jewels_count"] == 0
    assert body["highest_ease_chain"] is None


def test_dashboard_counts_nodes_and_edges_by_type(client):
    engagement = client.get("/api/engagements/active").json()
    asset = _create(client, "asset", name="a.com", asset_type="domain")
    finding = _create(client, "finding", title="F1", cvss_score=5.0)
    _edge(client, asset, finding, "HAS_FINDING")

    r = client.get(f"/api/engagements/{engagement['id']}/dashboard")
    body = r.json()
    assert body["total_nodes"] == 2
    assert body["total_edges"] == 1
    assert body["node_counts_by_type"] == {"asset": 1, "finding": 1}
    assert body["edge_counts_by_type"] == {"HAS_FINDING": 1}


def test_dashboard_reports_paths_to_crown_jewels_and_highest_ease_chain(client):
    engagement = client.get("/api/engagements/active").json()
    asset = _create(client, "asset", name="dev.client.com", asset_type="subdomain", is_entry_point=True)
    finding = _create(
        client, "finding", title="Easy XSS", cvss_score=7.0, exploit_public=True, auth_required=False
    )
    jewel = _create(client, "data_store", name="db", is_crown_jewel=True)
    _edge(client, asset, finding, "HAS_FINDING")
    _edge(client, finding, jewel, "YIELDS")

    r = client.get(f"/api/engagements/{engagement['id']}/dashboard")
    body = r.json()
    assert body["entry_point_count"] == 1
    assert body["crown_jewel_count"] == 1
    assert body["paths_to_crown_jewels_count"] == 1
    assert body["highest_ease_chain"] is not None
    assert body["highest_ease_chain"]["entry_point"]["id"] == asset
    assert body["highest_ease_chain"]["crown_jewel"]["id"] == jewel


def test_dashboard_isolated_per_engagement(client):
    a = client.post("/api/engagements", json={"name": "Client A"}).json()
    _create(client, "asset", name="a.com", asset_type="domain")

    b = client.post("/api/engagements", json={"name": "Client B"}).json()
    _create(client, "asset", name="b.com", asset_type="domain")
    _create(client, "asset", name="b2.com", asset_type="domain")

    dash_a = client.get(f"/api/engagements/{a['id']}/dashboard").json()
    dash_b = client.get(f"/api/engagements/{b['id']}/dashboard").json()
    assert dash_a["total_nodes"] == 1
    assert dash_b["total_nodes"] == 2


def test_dashboard_nonexistent_engagement_404(client):
    import uuid

    r = client.get(f"/api/engagements/{uuid.uuid4()}/dashboard")
    assert r.status_code == 404
