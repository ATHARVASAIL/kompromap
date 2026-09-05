"""Finding verification workflow.

Kompromap never decides on its own whether a finding is a false positive.
Determining that means *verifying the vulnerability* — sending the payload,
reading the response — and this tool never touches the target; it only
reads files handed to it. A heuristic guess presented as a verdict is
actively dangerous: if the tool says "probably a false positive", the
analyst skips verifying, and it was real, the report ships having missed a
live vulnerability because software sounded confident.

So the tool records the analyst's judgement and acts on it. The most
consequential action is exclusion from path-finding: a chain routed
through a false positive is a *fabricated* attack path, which is the worst
possible output because it looks exactly like a real one.
"""
import pytest

TRIVIAL = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"


def _node(client, node_type, **fields):
    r = client.post("/api/nodes", json={"node_type": node_type, **fields})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _edge(client, s, t, et):
    assert client.post(
        "/api/edges", json={"source_node_id": s, "target_node_id": t, "edge_type": et}
    ).status_code == 201


@pytest.fixture()
def chain(client):
    """entry -> finding -> crown jewel, with a second independent route."""
    entry = _node(client, "asset", name="api.test", asset_type="domain", is_entry_point=True)
    primary = _node(
        client, "finding", title="Log4Shell", cvss_score=10.0,
        cvss_vector=TRIVIAL, exploit_public=True, auth_required=False,
    )
    backup = _node(client, "finding", title="SQLi", cvss_score=7.0, auth_required=True)
    jewel = _node(client, "data_store", name="pii_db", is_crown_jewel=True)

    _edge(client, entry, primary, "HAS_FINDING")
    _edge(client, primary, jewel, "YIELDS")
    _edge(client, entry, backup, "HAS_FINDING")
    _edge(client, backup, jewel, "YIELDS")
    return {"entry": entry, "primary": primary, "backup": backup, "jewel": jewel}


def _paths(client):
    r = client.post("/api/pathfind/best", json={})
    assert r.status_code == 200, r.text
    return r.json()["paths"]


class TestDefaults:
    def test_findings_start_unverified(self, client):
        """Nothing imported has been triaged, and the tool must say so
        rather than implying confidence it doesn't have."""
        node_id = _node(client, "finding", title="F", cvss_score=5.0)
        assert client.get(f"/api/nodes/{node_id}").json()["verification_status"] == "unverified"

    def test_ingested_findings_are_also_unverified(self, client):
        with open("tests/fixtures/nuclei_sample.jsonl", "rb") as f:
            r = client.post("/api/ingest/nuclei", files={"file": ("n.jsonl", f, "application/json")})
        assert r.status_code == 200
        findings = client.get("/api/nodes?node_type=finding").json()
        assert findings
        assert all(f["verification_status"] == "unverified" for f in findings)


class TestTransitions:
    @pytest.mark.parametrize(
        "status", ["unverified", "confirmed", "false-positive", "needs-retest"]
    )
    def test_every_status_is_settable(self, client, status):
        node_id = _node(client, "finding", title="F", cvss_score=5.0)
        r = client.patch(f"/api/nodes/{node_id}", json={"verification_status": status})
        assert r.status_code == 200
        assert r.json()["verification_status"] == status

    def test_invalid_status_is_rejected(self, client):
        node_id = _node(client, "finding", title="F", cvss_score=5.0)
        r = client.patch(f"/api/nodes/{node_id}", json={"verification_status": "probably-fine"})
        assert r.status_code == 422

    def test_a_note_can_record_the_reasoning(self, client):
        """Why something was ruled out matters as much as the ruling."""
        node_id = _node(client, "finding", title="F", cvss_score=5.0)
        r = client.patch(
            f"/api/nodes/{node_id}",
            json={
                "verification_status": "false-positive",
                "verification_note": "WAF blocks the payload; 403 on every attempt.",
            },
        )
        assert r.status_code == 200
        assert "WAF blocks" in r.json()["verification_note"]

    def test_verification_is_independent_of_remediation_status(self, client):
        """`status` tracks whether it's fixed; `verification_status` tracks
        whether it's real. A finding can be confirmed-real and still open."""
        node_id = _node(client, "finding", title="F", cvss_score=5.0, status="open")
        client.patch(f"/api/nodes/{node_id}", json={"verification_status": "confirmed"})
        body = client.get(f"/api/nodes/{node_id}").json()
        assert body["status"] == "open"
        assert body["verification_status"] == "confirmed"


class TestPathfindingExclusion:
    def test_a_confirmed_finding_still_carries_its_chain(self, chain, client):
        client.patch(f"/api/nodes/{chain['primary']}", json={"verification_status": "confirmed"})
        assert _paths(client)

    def test_a_false_positive_stops_carrying_a_chain(self, chain, client):
        """The core guarantee. A chain through a finding the analyst ruled
        out is a fabricated attack path."""
        before = _paths(client)[0]
        assert before["total_cost"] < 1.0  # the cheap Log4Shell route

        client.patch(
            f"/api/nodes/{chain['primary']}", json={"verification_status": "false-positive"}
        )
        after = _paths(client)

        # The remaining route must be the other finding, not the excluded one.
        assert after
        labels = [n["label"] for n in after[0]["nodes"]]
        assert "Log4Shell" not in labels
        assert "SQLi" in labels

    def test_excluding_every_route_leaves_no_paths(self, chain, client):
        for key in ("primary", "backup"):
            client.patch(
                f"/api/nodes/{chain[key]}", json={"verification_status": "false-positive"}
            )
        assert _paths(client) == []

    def test_an_excluded_path_is_dropped_not_reported_at_absurd_cost(self, chain, client):
        """edge_cost marks these impassable rather than deleting the edge,
        so the pathfinder must filter them out — otherwise a nonsense
        1e6-cost 'path' would still appear in the results."""
        for key in ("primary", "backup"):
            client.patch(
                f"/api/nodes/{chain[key]}", json={"verification_status": "false-positive"}
            )
        assert all(p["total_cost"] < 1000 for p in _paths(client))

    def test_exclusion_survives_a_manual_edge_weight(self, client):
        """An analyst's false-positive ruling must beat a stale hand-set
        weight on the same edge."""
        entry = _node(client, "asset", name="a.test", asset_type="domain", is_entry_point=True)
        finding = _node(client, "finding", title="F", cvss_score=10.0, cvss_vector=TRIVIAL)
        jewel = _node(client, "data_store", name="db", is_crown_jewel=True)
        _edge(client, entry, finding, "HAS_FINDING")
        client.post(
            "/api/edges",
            json={
                "source_node_id": finding,
                "target_node_id": jewel,
                "edge_type": "YIELDS",
                "weight": 0.95,
            },
        )
        assert _paths(client)
        client.patch(f"/api/nodes/{finding}", json={"verification_status": "false-positive"})
        assert _paths(client) == []

    def test_reversing_a_false_positive_restores_the_chain(self, chain, client):
        client.patch(
            f"/api/nodes/{chain['primary']}", json={"verification_status": "false-positive"}
        )
        client.patch(f"/api/nodes/{chain['primary']}", json={"verification_status": "confirmed"})
        labels = [n["label"] for n in _paths(client)[0]["nodes"]]
        assert "Log4Shell" in labels


class TestReporting:
    def test_report_states_verification_coverage(self, chain, client):
        """An honest caveat about how much was actually triaged, rather
        than a fabricated verdict on each finding."""
        r = client.post("/api/reports/engagement", json={"format": "json"})
        assert r.status_code == 200
        caveats = " ".join(r.json()["data"]["caveats"])
        assert "verif" in caveats.lower()

    def test_report_excludes_false_positive_chains(self, chain, client):
        client.patch(
            f"/api/nodes/{chain['primary']}", json={"verification_status": "false-positive"}
        )
        data = client.post("/api/reports/engagement", json={"format": "json"}).json()["data"]
        for c in data["chains"]:
            assert all(s["from"] != "Log4Shell" for s in c["steps"])
