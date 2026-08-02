"""Input-validation guards on the node schemas.

Both of these were found by fuzzing the API rather than reading the code:
CVSS accepted -5 and 999, and ports accepted 0 and 70000. Neither is
merely cosmetic — severityFromCvss() bands on the raw value and the
path-finding ease score normalizes by dividing by 10, so an out-of-range
CVSS silently corrupts both severity display and path ranking.
"""
import pytest


@pytest.mark.parametrize("score", [-5, -0.1, 10.1, 999, 1e9])
def test_cvss_out_of_range_is_rejected(client, score):
    r = client.post("/api/nodes", json={"node_type": "finding", "title": "t", "cvss_score": score})
    assert r.status_code == 422


@pytest.mark.parametrize("score", [0, 0.1, 5.5, 9.9, 10])
def test_cvss_in_range_is_accepted(client, score):
    r = client.post("/api/nodes", json={"node_type": "finding", "title": "t", "cvss_score": score})
    assert r.status_code == 201


def test_cvss_may_be_omitted(client):
    """Plenty of real findings have no CVSS — null must stay valid."""
    r = client.post("/api/nodes", json={"node_type": "finding", "title": "t"})
    assert r.status_code == 201


@pytest.mark.parametrize("port", [0, -1, 65536, 70000])
def test_port_out_of_range_is_rejected(client, port):
    r = client.post("/api/nodes", json={"node_type": "service", "port": port, "protocol": "tcp"})
    assert r.status_code == 422


@pytest.mark.parametrize("port", [1, 80, 443, 8080, 65535])
def test_port_in_range_is_accepted(client, port):
    r = client.post("/api/nodes", json={"node_type": "service", "port": port, "protocol": "tcp"})
    assert r.status_code == 201


def test_cvss_validation_also_applies_on_update(client):
    created = client.post("/api/nodes", json={"node_type": "finding", "title": "t", "cvss_score": 5.0})
    node_id = created.json()["id"]
    assert client.patch(f"/api/nodes/{node_id}", json={"cvss_score": 999}).status_code == 422
    assert client.patch(f"/api/nodes/{node_id}", json={"cvss_score": 8.5}).status_code == 200
