from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_ingest_nmap_file(client):
    with open(FIXTURES / "nmap_sample.xml", "rb") as f:
        r = client.post("/api/ingest/nmap", files={"file": ("nmap_sample.xml", f, "application/xml")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assets_created"] == 2
    assert body["services_created"] == 3


def test_ingest_nuclei_file(client):
    with open(FIXTURES / "nuclei_sample.jsonl", "rb") as f:
        r = client.post("/api/ingest/nuclei", files={"file": ("nuclei_sample.jsonl", f, "application/json")})
    assert r.status_code == 200, r.text
    assert r.json()["findings_created"] == 3


def test_ingest_amass_file(client):
    with open(FIXTURES / "amass_sample.txt", "rb") as f:
        r = client.post("/api/ingest/amass", files={"file": ("amass_sample.txt", f, "text/plain")})
    assert r.status_code == 200, r.text
    assert r.json()["assets_created"] == 4


def test_ingest_burp_file(client):
    with open(FIXTURES / "burp_sample.xml", "rb") as f:
        r = client.post("/api/ingest/burp", files={"file": ("burp_sample.xml", f, "application/xml")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["endpoints_created"] == 3
    assert body["findings_created"] == 3


def test_ingest_rejects_empty_file(client):
    r = client.post("/api/ingest/nmap", files={"file": ("empty.xml", b"", "application/xml")})
    assert r.status_code == 422


def test_ingest_rejects_garbage_xml(client):
    r = client.post(
        "/api/ingest/nmap", files={"file": ("bad.xml", b"not xml at all {{{", "application/xml")}
    )
    assert r.status_code == 422


def test_full_workflow_end_to_end(client):
    """Ingest nmap + burp for the same host, then check the graph endpoint
    reflects the combined result — exercises ingestion + graph together."""
    with open(FIXTURES / "nmap_sample.xml", "rb") as f:
        client.post("/api/ingest/nmap", files={"file": ("nmap_sample.xml", f, "application/xml")})
    with open(FIXTURES / "burp_sample.xml", "rb") as f:
        client.post("/api/ingest/burp", files={"file": ("burp_sample.xml", f, "application/xml")})

    r = client.get("/api/graph")
    assert r.status_code == 200
    body = r.json()

    node_types = {n["node_type"] for n in body["nodes"]}
    assert {"asset", "service", "endpoint", "finding"}.issubset(node_types)

    edge_types = {e["edge_type"] for e in body["edges"]}
    assert {"HOSTS", "EXPOSES", "HAS_FINDING"}.issubset(edge_types)

    # Burp endpoints should be exposed by the https service ingested from nmap
    # (dev.client.com has both an nmap-discovered :443 service and burp findings)
    https_service = next(n for n in body["nodes"] if n["node_type"] == "service" and n["properties"]["port"] == 443)
    exposes_edges = [e for e in body["edges"] if e["edge_type"] == "EXPOSES"]
    assert any(e["source"] == https_service["id"] for e in exposes_edges)
