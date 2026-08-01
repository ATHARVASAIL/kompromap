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
    return r.json()["id"]


def _build_chain(client):
    asset = _create(client, "asset", name="dev.client.com", asset_type="subdomain")
    finding = _create(
        client,
        "finding",
        title="Subdomain takeover",
        cvss_score=8.1,
        exploit_public=True,
        auth_required=False,
        evidence="dig CNAME confirmed dangling record",
    )
    jewel = _create(client, "data_store", name="users_db", data_classification="PII")
    _edge(client, asset, finding, "HAS_FINDING")
    _edge(client, finding, jewel, "YIELDS")
    return asset, finding, jewel


def test_narrative_without_api_key_uses_template(client):
    asset, finding, jewel = _build_chain(client)
    r = client.post("/api/reports/narrative", json={"node_ids": [asset, finding, jewel]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["narrative_source"] == "template"
    assert "dev.client.com" in body["narrative"]


def test_narrative_rejects_disconnected_chain(client):
    asset, finding, jewel = _build_chain(client)
    r = client.post("/api/reports/narrative", json={"node_ids": [asset, jewel]})
    assert r.status_code == 422


def test_narrative_rejects_nonexistent_node(client):
    import uuid

    asset, finding, jewel = _build_chain(client)
    r = client.post("/api/reports/narrative", json={"node_ids": [asset, str(uuid.uuid4())]})
    assert r.status_code == 422


def test_export_markdown_format(client):
    asset, finding, jewel = _build_chain(client)
    r = client.post(
        "/api/reports/export", json={"node_ids": [asset, finding, jewel], "format": "markdown"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["format"] == "markdown"
    assert body["content"].startswith("# Attack Chain:")
    assert "Subdomain takeover" in body["content"]
    assert body["data"] is None


def test_export_json_format(client):
    asset, finding, jewel = _build_chain(client)
    r = client.post("/api/reports/export", json={"node_ids": [asset, finding, jewel], "format": "json"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["format"] == "json"
    assert body["content"] is None
    assert body["data"]["entry_point"]["label"] == "dev.client.com"
    assert body["data"]["crown_jewel"]["label"] == "users_db"
    assert len(body["data"]["steps"]) == 3


def test_export_reuses_provided_narrative_without_regenerating(client):
    asset, finding, jewel = _build_chain(client)
    r = client.post(
        "/api/reports/export",
        json={
            "node_ids": [asset, finding, jewel],
            "narrative": "A custom pre-reviewed narrative.",
            "format": "json",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["narrative"] == "A custom pre-reviewed narrative."


def test_export_rejects_disconnected_chain(client):
    asset, finding, jewel = _build_chain(client)
    r = client.post("/api/reports/export", json={"node_ids": [asset, jewel], "format": "markdown"})
    assert r.status_code == 422
