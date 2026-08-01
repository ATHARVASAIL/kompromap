def test_active_engagement_auto_created_on_first_use(client):
    r = client.get("/api/engagements/active")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Default Engagement"
    assert r.json()["is_active"] is True


def test_create_engagement_activates_by_default(client):
    r = client.post("/api/engagements", json={"name": "Client A", "client_name": "Acme Corp"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Client A"
    assert body["client_name"] == "Acme Corp"
    assert body["is_active"] is True

    r = client.get("/api/engagements/active")
    assert r.json()["id"] == body["id"]


def test_create_engagement_without_activating(client):
    default = client.get("/api/engagements/active").json()

    r = client.post("/api/engagements", json={"name": "Client B", "activate": False})
    assert r.status_code == 201
    assert r.json()["is_active"] is False

    assert client.get("/api/engagements/active").json()["id"] == default["id"]


def test_list_engagements_includes_default_when_nothing_else_created_first(client):
    client.get("/api/engagements/active")  # establishes the default before anything else exists
    client.post("/api/engagements", json={"name": "Client A"})
    r = client.get("/api/engagements")
    names = {e["name"] for e in r.json()}
    assert "Default Engagement" in names
    assert "Client A" in names


def test_activate_switches_active_engagement(client):
    a = client.post("/api/engagements", json={"name": "Client A"}).json()
    b = client.post("/api/engagements", json={"name": "Client B", "activate": False}).json()

    r = client.post(f"/api/engagements/{b['id']}/activate")
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    a_refreshed = client.get(f"/api/engagements/{a['id']}").json()
    assert a_refreshed["is_active"] is False


def test_activate_nonexistent_engagement_404(client):
    import uuid

    r = client.post(f"/api/engagements/{uuid.uuid4()}/activate")
    assert r.status_code == 404


def test_update_engagement_rename(client):
    e = client.post("/api/engagements", json={"name": "Client A"}).json()
    r = client.patch(f"/api/engagements/{e['id']}", json={"name": "Client A (renamed)"})
    assert r.status_code == 200
    assert r.json()["name"] == "Client A (renamed)"


def test_delete_empty_engagement(client):
    e = client.post("/api/engagements", json={"name": "Empty Client", "activate": False}).json()
    r = client.delete(f"/api/engagements/{e['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/engagements/{e['id']}").status_code == 404


def test_delete_populated_engagement_is_blocked(client):
    e = client.post("/api/engagements", json={"name": "Populated Client"}).json()
    r = client.post("/api/nodes", json={"node_type": "asset", "name": "x.com", "asset_type": "domain"})
    assert r.status_code == 201

    r = client.delete(f"/api/engagements/{e['id']}")
    assert r.status_code == 409


def test_new_node_defaults_to_active_engagement(client):
    e = client.post("/api/engagements", json={"name": "Client A"}).json()
    r = client.post("/api/nodes", json={"node_type": "asset", "name": "x.com", "asset_type": "domain"})
    assert r.json()["engagement_id"] == e["id"]


def test_node_creation_accepts_explicit_engagement_id_override(client):
    a = client.post("/api/engagements", json={"name": "Client A"}).json()
    b = client.post("/api/engagements", json={"name": "Client B", "activate": False}).json()

    # Client A is active, but we explicitly target Client B
    r = client.post(
        "/api/nodes",
        json={"node_type": "asset", "name": "x.com", "asset_type": "domain", "engagement_id": b["id"]},
    )
    assert r.json()["engagement_id"] == b["id"]


def test_graph_endpoint_isolates_engagements(client):
    a = client.post("/api/engagements", json={"name": "Client A"}).json()
    client.post("/api/nodes", json={"node_type": "asset", "name": "a-asset.com", "asset_type": "domain"})

    b = client.post("/api/engagements", json={"name": "Client B"}).json()
    client.post("/api/nodes", json={"node_type": "asset", "name": "b-asset.com", "asset_type": "domain"})

    graph_a = client.get("/api/graph", params={"engagement_id": a["id"]}).json()
    graph_b = client.get("/api/graph", params={"engagement_id": b["id"]}).json()

    a_names = {n["label"] for n in graph_a["nodes"]}
    b_names = {n["label"] for n in graph_b["nodes"]}
    assert a_names == {"a-asset.com"}
    assert b_names == {"b-asset.com"}
