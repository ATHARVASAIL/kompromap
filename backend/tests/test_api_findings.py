def test_create_finding_via_findings_endpoint(client):
    r = client.post("/api/nodes", json={"node_type": "asset", "name": "dev.client.com", "asset_type": "subdomain"})
    asset_id = r.json()["id"]

    r = client.post(
        "/api/findings",
        json={
            "title": "Subdomain takeover",
            "target_node_id": asset_id,
            "cvss_score": 8.1,
            "exploit_public": True,
            "auth_required": False,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Subdomain takeover"
    assert body["node_type"] == "finding"

    edges = client.get("/api/edges", params={"target_node_id": body["id"]}).json()
    assert len(edges) == 1
    assert edges[0]["edge_type"] == "HAS_FINDING"
    assert edges[0]["source_node_id"] == asset_id


def test_finding_can_attach_to_endpoint(client):
    r = client.post("/api/nodes", json={"node_type": "endpoint", "path": "/admin/login"})
    endpoint_id = r.json()["id"]

    r = client.post(
        "/api/findings",
        json={"title": "Stored XSS", "target_node_id": endpoint_id},
    )
    assert r.status_code == 201


def test_finding_rejects_non_asset_endpoint_target(client):
    r = client.post("/api/nodes", json={"node_type": "account", "username": "admin"})
    account_id = r.json()["id"]

    r = client.post(
        "/api/findings",
        json={"title": "Bad target", "target_node_id": account_id},
    )
    assert r.status_code == 422


def test_finding_rejects_nonexistent_target(client):
    import uuid

    r = client.post(
        "/api/findings",
        json={"title": "Orphan", "target_node_id": str(uuid.uuid4())},
    )
    assert r.status_code == 422
