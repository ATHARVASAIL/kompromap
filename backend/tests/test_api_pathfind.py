def _create(client, node_type, **fields):
    r = client.post("/api/nodes", json={"node_type": node_type, **fields})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _edge(client, source_id, target_id, edge_type, weight=None):
    payload = {"source_node_id": source_id, "target_node_id": target_id, "edge_type": edge_type}
    if weight is not None:
        payload["weight"] = weight
    r = client.post("/api/edges", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _build_spec_example_chain(client):
    """The exact chain from spec §1:
    subdomain takeover -> stored XSS -> session cookie theft -> IDOR -> PII dump
    """
    asset = _create(client, "asset", name="dev.client.com", asset_type="subdomain", is_entry_point=True)
    takeover_finding = _create(
        client, "finding", title="Subdomain takeover", cvss_score=8.1, exploit_public=True, auth_required=False
    )
    admin_endpoint = _create(client, "endpoint", path="/admin/login")
    xss_finding = _create(
        client, "finding", title="Stored XSS on admin login page", cvss_score=6.5, exploit_public=True, auth_required=False
    )
    session_cred = _create(client, "credential", cred_type="session_token", scope="admin")
    users_endpoint = _create(client, "endpoint", path="/api/v2/users/{id}")
    idor_finding = _create(
        client, "finding", title="IDOR on /api/v2/users/{id}", cvss_score=7.5, exploit_public=False, auth_required=True
    )
    pii_datastore = _create(
        client, "data_store", name="users_db", data_classification="PII", record_count_estimate=40000, is_crown_jewel=True
    )

    _edge(client, asset, takeover_finding, "HAS_FINDING")
    _edge(client, takeover_finding, admin_endpoint, "YIELDS")
    _edge(client, admin_endpoint, xss_finding, "HAS_FINDING")
    _edge(client, xss_finding, session_cred, "YIELDS")
    _edge(client, session_cred, users_endpoint, "GRANTS_ACCESS_TO")
    _edge(client, users_endpoint, idor_finding, "HAS_FINDING")
    _edge(client, idor_finding, pii_datastore, "YIELDS")

    return {
        "asset": asset,
        "pii_datastore": pii_datastore,
        "takeover_finding": takeover_finding,
        "xss_finding": xss_finding,
        "idor_finding": idor_finding,
    }


def test_pathfind_best_finds_the_full_spec_example_chain(client):
    ids = _build_spec_example_chain(client)

    r = client.post("/api/pathfind/best", json={})
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["paths"]) == 1
    path = body["paths"][0]
    assert path["entry_point"]["id"] == ids["asset"]
    assert path["crown_jewel"]["id"] == ids["pii_datastore"]

    node_ids_in_path = [n["id"] for n in path["nodes"]]
    assert node_ids_in_path[0] == ids["asset"]
    assert node_ids_in_path[-1] == ids["pii_datastore"]
    assert ids["takeover_finding"] in node_ids_in_path
    assert ids["xss_finding"] in node_ids_in_path
    assert ids["idor_finding"] in node_ids_in_path
    assert body["unreachable_entry_points"] == []


def test_pathfind_best_requires_entry_points(client):
    _create(client, "data_store", name="db", is_crown_jewel=True)
    r = client.post("/api/pathfind/best", json={})
    assert r.status_code == 422


def test_pathfind_best_requires_crown_jewels(client):
    _create(client, "asset", name="x.com", asset_type="domain", is_entry_point=True)
    r = client.post("/api/pathfind/best", json={})
    assert r.status_code == 422


def test_pathfind_best_reports_unreachable_entry_point(client):
    reachable_entry = _create(client, "asset", name="a.com", asset_type="domain", is_entry_point=True)
    isolated_entry = _create(client, "asset", name="b.com", asset_type="domain", is_entry_point=True)
    jewel = _create(client, "data_store", name="db", is_crown_jewel=True)
    finding = _create(client, "finding", title="F", cvss_score=5.0)

    _edge(client, reachable_entry, finding, "HAS_FINDING")
    _edge(client, finding, jewel, "YIELDS")

    r = client.post("/api/pathfind/best", json={})
    body = r.json()
    assert len(body["paths"]) == 1
    assert body["paths"][0]["entry_point"]["id"] == reachable_entry
    assert len(body["unreachable_entry_points"]) == 1
    assert body["unreachable_entry_points"][0]["id"] == isolated_entry


def test_pathfind_from_specific_entry_point(client):
    ids = _build_spec_example_chain(client)

    r = client.post(f"/api/pathfind/from/{ids['asset']}", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["paths"]) == 1
    assert body["paths"][0]["crown_jewel"]["id"] == ids["pii_datastore"]
    assert body["unreachable_crown_jewels"] == []


def test_pathfind_from_reports_unreachable_crown_jewel(client):
    entry = _create(client, "asset", name="a.com", asset_type="domain", is_entry_point=True)
    reachable_jewel = _create(client, "data_store", name="db1", is_crown_jewel=True)
    isolated_jewel = _create(client, "data_store", name="db2", is_crown_jewel=True)
    finding = _create(client, "finding", title="F", cvss_score=5.0)

    _edge(client, entry, finding, "HAS_FINDING")
    _edge(client, finding, reachable_jewel, "YIELDS")

    r = client.post(f"/api/pathfind/from/{entry}", json={})
    body = r.json()
    assert len(body["paths"]) == 1
    assert len(body["unreachable_crown_jewels"]) == 1
    assert body["unreachable_crown_jewels"][0]["id"] == isolated_jewel


def test_pathfind_from_nonexistent_entry_point_404(client):
    import uuid

    _create(client, "data_store", name="db", is_crown_jewel=True)
    r = client.post(f"/api/pathfind/from/{uuid.uuid4()}", json={})
    assert r.status_code == 404


def test_pathfind_accepts_explicit_ids_overriding_tags(client):
    entry = _create(client, "asset", name="a.com", asset_type="domain")  # not tagged
    jewel = _create(client, "data_store", name="db")  # not tagged
    finding = _create(client, "finding", title="F", cvss_score=5.0)
    _edge(client, entry, finding, "HAS_FINDING")
    _edge(client, finding, jewel, "YIELDS")

    r = client.post(
        "/api/pathfind/best",
        json={"entry_point_ids": [entry], "crown_jewel_ids": [jewel]},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["paths"]) == 1


def test_pathfind_custom_weights_change_result(client):
    entry = _create(client, "asset", name="a.com", asset_type="domain", is_entry_point=True)
    jewel = _create(client, "data_store", name="db", is_crown_jewel=True)
    finding = _create(client, "finding", title="F", cvss_score=1.0, exploit_public=False, auth_required=True)
    _edge(client, entry, finding, "HAS_FINDING")
    _edge(client, finding, jewel, "YIELDS")

    # default weights -> low ease score -> high cost
    r_default = client.post("/api/pathfind/best", json={})
    default_cost = r_default.json()["paths"][0]["total_cost"]

    # weight everything toward complexity with default_complexity=0 (trivial) -> much lower cost
    r_custom = client.post(
        "/api/pathfind/best",
        json={"weights": {"cvss": 0, "exploit_public": 0, "auth_required": 0, "complexity": 1, "default_complexity": 0}},
    )
    custom_cost = r_custom.json()["paths"][0]["total_cost"]

    assert custom_cost < default_cost
