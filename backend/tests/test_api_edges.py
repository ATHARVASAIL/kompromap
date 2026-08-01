def _make_asset(client, name="dev.client.com"):
    r = client.post("/api/nodes", json={"node_type": "asset", "name": name, "asset_type": "subdomain"})
    return r.json()["id"]


def _make_service(client, port=443):
    r = client.post("/api/nodes", json={"node_type": "service", "port": port, "protocol": "tcp"})
    return r.json()["id"]


def test_create_edge_between_existing_nodes(client):
    asset_id = _make_asset(client)
    service_id = _make_service(client)

    r = client.post(
        "/api/edges",
        json={"source_node_id": asset_id, "target_node_id": service_id, "edge_type": "HOSTS"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["edge_type"] == "HOSTS"


def test_create_edge_rejects_missing_node(client):
    import uuid

    asset_id = _make_asset(client)
    r = client.post(
        "/api/edges",
        json={"source_node_id": asset_id, "target_node_id": str(uuid.uuid4()), "edge_type": "HOSTS"},
    )
    assert r.status_code == 422


def test_list_edges_filters_by_source(client):
    asset_id = _make_asset(client)
    service_id = _make_service(client)
    client.post(
        "/api/edges",
        json={"source_node_id": asset_id, "target_node_id": service_id, "edge_type": "HOSTS"},
    )

    r = client.get("/api/edges", params={"source_node_id": asset_id})
    assert len(r.json()) == 1


def test_edge_metadata_round_trips(client):
    asset_id = _make_asset(client)
    service_id = _make_service(client)
    r = client.post(
        "/api/edges",
        json={
            "source_node_id": asset_id,
            "target_node_id": service_id,
            "edge_type": "HOSTS",
            "weight": 0.8,
            "metadata": {"note": "confirmed manually"},
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["weight"] == 0.8
    assert body["metadata"] == {"note": "confirmed manually"}


def test_delete_edge(client):
    asset_id = _make_asset(client)
    service_id = _make_service(client)
    r = client.post(
        "/api/edges",
        json={"source_node_id": asset_id, "target_node_id": service_id, "edge_type": "HOSTS"},
    )
    edge_id = r.json()["id"]

    r = client.delete(f"/api/edges/{edge_id}")
    assert r.status_code == 204
    assert client.get(f"/api/edges/{edge_id}").status_code == 404
