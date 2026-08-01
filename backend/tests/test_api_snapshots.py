def _create_asset(client, name):
    r = client.post("/api/nodes", json={"node_type": "asset", "name": name, "asset_type": "domain"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_create_snapshot_captures_current_graph(client):
    engagement = client.get("/api/engagements/active").json()
    _create_asset(client, "a.com")
    _create_asset(client, "b.com")

    r = client.post(f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Kickoff"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["label"] == "Kickoff"
    assert body["node_count"] == 2
    assert body["edge_count"] == 0


def test_list_snapshots_for_engagement(client):
    engagement = client.get("/api/engagements/active").json()
    _create_asset(client, "a.com")
    client.post(f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Day 1"})
    client.post(f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Day 2"})

    r = client.get(f"/api/engagements/{engagement['id']}/snapshots")
    assert r.status_code == 200
    labels = {s["label"] for s in r.json()}
    assert labels == {"Day 1", "Day 2"}


def test_get_snapshot_includes_full_graph_data(client):
    engagement = client.get("/api/engagements/active").json()
    _create_asset(client, "a.com")
    created = client.post(f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Kickoff"}).json()

    r = client.get(f"/api/snapshots/{created['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["data"]["nodes"]) == 1
    assert body["data"]["nodes"][0]["label"] == "a.com"


def test_diff_snapshot_against_current_shows_added_nodes(client):
    engagement = client.get("/api/engagements/active").json()
    _create_asset(client, "a.com")
    snapshot = client.post(
        f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Kickoff"}
    ).json()

    _create_asset(client, "b.com")  # added after the snapshot was taken

    r = client.get(f"/api/snapshots/{snapshot['id']}/diff")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["nodes_added"]) == 1
    assert body["nodes_added"][0]["label"] == "b.com"
    assert body["nodes_removed"] == []


def test_diff_snapshot_against_current_shows_removed_nodes(client):
    engagement = client.get("/api/engagements/active").json()
    asset_id = _create_asset(client, "a.com")
    snapshot = client.post(
        f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Kickoff"}
    ).json()

    client.delete(f"/api/nodes/{asset_id}")

    r = client.get(f"/api/snapshots/{snapshot['id']}/diff")
    body = r.json()
    assert len(body["nodes_removed"]) == 1
    assert body["nodes_removed"][0]["label"] == "a.com"
    assert body["nodes_added"] == []


def test_diff_between_two_snapshots(client):
    engagement = client.get("/api/engagements/active").json()
    _create_asset(client, "a.com")
    snap1 = client.post(f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Day 1"}).json()

    _create_asset(client, "b.com")
    snap2 = client.post(f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Day 2"}).json()

    r = client.get(f"/api/snapshots/{snap1['id']}/diff", params={"compare_to": snap2["id"]})
    body = r.json()
    assert len(body["nodes_added"]) == 1
    assert body["nodes_added"][0]["label"] == "b.com"


def test_snapshot_isolated_per_engagement(client):
    a = client.post("/api/engagements", json={"name": "Client A"}).json()
    _create_asset(client, "a-only.com")

    b = client.post("/api/engagements", json={"name": "Client B"}).json()
    _create_asset(client, "b-only.com")

    snap_a = client.post(f"/api/engagements/{a['id']}/snapshots", json={"label": "A snapshot"}).json()
    labels = {n["label"] for n in client.get(f"/api/snapshots/{snap_a['id']}").json()["data"]["nodes"]}
    assert labels == {"a-only.com"}


def test_delete_snapshot(client):
    engagement = client.get("/api/engagements/active").json()
    _create_asset(client, "a.com")
    snapshot = client.post(
        f"/api/engagements/{engagement['id']}/snapshots", json={"label": "Kickoff"}
    ).json()

    r = client.delete(f"/api/snapshots/{snapshot['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/snapshots/{snapshot['id']}").status_code == 404


def test_snapshot_nonexistent_engagement_404(client):
    import uuid

    r = client.post(f"/api/engagements/{uuid.uuid4()}/snapshots", json={"label": "X"})
    assert r.status_code == 404
