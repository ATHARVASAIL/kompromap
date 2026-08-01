def test_create_and_get_asset(client):
    r = client.post(
        "/api/nodes",
        json={
            "node_type": "asset",
            "name": "dev.client.com",
            "asset_type": "subdomain",
            "tags": ["scope:web"],
            "is_entry_point": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "dev.client.com"
    assert body["is_entry_point"] is True

    r = client.get(f"/api/nodes/{body['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "dev.client.com"


def test_list_nodes_filters_by_type(client):
    client.post("/api/nodes", json={"node_type": "asset", "name": "a.com", "asset_type": "domain"})
    client.post(
        "/api/nodes",
        json={"node_type": "account", "username": "admin", "privilege_level": "admin"},
    )

    r = client.get("/api/nodes", params={"node_type": "asset"})
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["node_type"] == "asset"


def test_list_nodes_filters_by_in_scope(client):
    client.post(
        "/api/nodes",
        json={"node_type": "asset", "name": "in.com", "asset_type": "domain", "in_scope": True},
    )
    client.post(
        "/api/nodes",
        json={"node_type": "asset", "name": "out.com", "asset_type": "domain", "in_scope": False},
    )

    r = client.get("/api/nodes", params={"node_type": "asset", "in_scope": True})
    names = {n["name"] for n in r.json()}
    assert names == {"in.com"}


def test_update_node_partial(client):
    r = client.post("/api/nodes", json={"node_type": "asset", "name": "x.com", "asset_type": "domain"})
    node_id = r.json()["id"]

    r = client.patch(f"/api/nodes/{node_id}", json={"is_crown_jewel": True})
    assert r.status_code == 200
    assert r.json()["is_crown_jewel"] is True
    assert r.json()["name"] == "x.com"  # untouched fields preserved


def test_delete_node(client):
    r = client.post("/api/nodes", json={"node_type": "asset", "name": "gone.com", "asset_type": "domain"})
    node_id = r.json()["id"]

    r = client.delete(f"/api/nodes/{node_id}")
    assert r.status_code == 204

    r = client.get(f"/api/nodes/{node_id}")
    assert r.status_code == 404


def test_get_nonexistent_node_404(client):
    import uuid

    r = client.get(f"/api/nodes/{uuid.uuid4()}")
    assert r.status_code == 404


def test_create_node_rejects_unknown_type(client):
    r = client.post("/api/nodes", json={"node_type": "not_a_type", "name": "x"})
    assert r.status_code == 422
