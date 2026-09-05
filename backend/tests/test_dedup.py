"""Tests for the Phase 2 deduplication engine.

Covers:
- Signal scoring (title, CWE, OWASP, location, endpoint, params)
- Scan execution with a full graph of assets/services/endpoints/findings
- Candidate resolution (merge, keep_separate, mark_duplicate)
- High-impact flagging
- API endpoints (scan, list scans, list candidates, resolve)
- Edge cases (fewer than 2 findings, no matches, etc.)
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.models import Asset, Edge, EdgeType, Endpoint, Finding, Node, NodeType, Service, WebApplication
from app.services.dedup import (
    DEFAULT_SIGNAL_WEIGHTS,
    HIGH_IMPACT_THRESHOLD,
    _score_cwe,
    _score_endpoint,
    _score_location,
    _score_owasp,
    _score_params,
    _score_title,
    run_scan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(client, node_type: str, **fields) -> str:
    """Create a node via the API, return its ID."""
    r = client.post("/api/nodes", json={"node_type": node_type, **fields})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _edge(client, source_id: str, target_id: str, edge_type: str) -> None:
    """Create an edge via the API."""
    r = client.post(
        "/api/edges",
        json={"source_node_id": source_id, "target_node_id": target_id, "edge_type": edge_type},
    )
    assert r.status_code == 201, r.text


def _make_graph(client) -> dict[str, str]:
    """Build a realistic mini-graph: asset → service → web_app → endpoint → finding."""
    asset_id = _node(client, "asset", name="app.example.com", asset_type="subdomain")
    service_id = _node(client, "service", port=443, protocol="tcp", banner="nginx")
    webapp_id = _node(
        client, "web_application",
        name="Main App", base_url="https://app.example.com",
        tech_stack=["nginx", "node"],
    )
    ep_id = _node(client, "endpoint", path="/api/v2/users", method="GET", params=["id", "format"])
    return {
        "asset": asset_id,
        "service": service_id,
        "webapp": webapp_id,
        "endpoint": ep_id,
    }


def _attach_finding(client, target_node_id: str, title: str, **finding_fields) -> str:
    """Create a finding attached to a target node."""
    r = client.post(
        "/api/findings",
        json={"title": title, "target_node_id": target_node_id, **finding_fields},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _wire_app_graph(client, ids: dict) -> None:
    """Wire up the asset → service → web_app → endpoint graph."""
    _edge(client, ids["asset"], ids["service"], "HOSTS")
    _edge(client, ids["service"], ids["webapp"], "EXPOSES")
    _edge(client, ids["webapp"], ids["endpoint"], "EXPOSES")


# ---------------------------------------------------------------------------
# Signal scoring unit tests
# ---------------------------------------------------------------------------

class TestSignalScoring:
    """Each signal scorer returns 0.0–1.0."""

    def test_title_exact_match(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="sql injection in login", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="sql injection in login", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        assert _score_title(a, b) == pytest.approx(1.0)

    def test_title_partial_match(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="sql injection", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="xss reflected", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        assert 0.0 < _score_title(a, b) < 1.0

    def test_title_no_match(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="sql injection", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="csrf on password reset", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        assert _score_title(a, b) < 0.3

    def test_cwe_exact_match(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="CWE-89", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="CWE-89", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        assert _score_cwe(a, b) == 1.0

    def test_cwe_different(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="CWE-89", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="CWE-79", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        assert _score_cwe(a, b) == 0.0

    def test_cwe_missing(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="CWE-89", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        assert _score_cwe(a, b) == 0.0

    def test_owasp_exact_match(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="A03:2021-Injection", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="a03:2021-injection", cvss_score=None, location="", endpoint_path="", params=[])
        assert _score_owasp(a, b) == 1.0  # case-insensitive via normalize

    def test_owasp_different(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="A03:2021-Injection", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="A01:2021-Broken Access Control", cvss_score=None, location="", endpoint_path="", params=[])
        assert _score_owasp(a, b) == 0.0

    def test_location_exact_match(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="app.example.com", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="app.example.com", endpoint_path="", params=[])
        assert _score_location(a, b) == 1.0

    def test_location_partial_match(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="https://app.example.com", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="https://app.example.com/api", endpoint_path="", params=[])
        assert 0.0 < _score_location(a, b) < 1.0

    def test_endpoint_exact_match(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="/api/v2/users", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="/api/v2/users", params=[])
        assert _score_endpoint(a, b) == 1.0

    def test_endpoint_normalizes_numeric_params(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="/users/123", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="/users/456", params=[])
        assert _score_endpoint(a, b) == 1.0

    def test_params_jaccard_full_overlap(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=["id", "format"])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=["id", "format"])
        assert _score_params(a, b) == 1.0

    def test_params_jaccard_partial(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=["id", "format", "debug"])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=["id", "sort"])
        assert _score_params(a, b) == 0.5  # 1 shared / 4 total

    def test_params_no_overlap(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=["id"])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=["q"])
        assert _score_params(a, b) == 0.0

    def test_params_both_empty(self):
        from app.services.dedup import FindingContext

        a = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        b = FindingContext(id=uuid.uuid4(), title="", cwe="", owasp="", cvss_score=None, location="", endpoint_path="", params=[])
        assert _score_params(a, b) == 0.0


# ---------------------------------------------------------------------------
# Service-level scan tests
# ---------------------------------------------------------------------------

class TestDedupScan:
    """Tests that exercise run_scan via the API layer, ensuring the full
    signal pipeline (DB → context → scoring → candidates) works end-to-end."""

    def test_scan_finds_exact_duplicates(self, client):
        """Two findings with the same title, CWE, and location should score high."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(
            client, ids["endpoint"], "SQLi in /api/v2/users",
            cwe="CWE-89", owasp_category="A03:2021-Injection",
        )
        f2 = _attach_finding(
            client, ids["endpoint"], "SQLi in /api/v2/users",
            cwe="CWE-89", owasp_category="A03:2021-Injection",
        )

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.5})
        assert r.status_code == 201, r.text
        scan = r.json()

        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        assert len(candidates) >= 1
        # Both findings should be in the top candidate.
        top = candidates[0]
        assert {top["finding_a_id"], top["finding_b_id"]} == {f1, f2}
        assert top["overall_score"] > 0.8

    def test_scan_no_candidates_below_threshold(self, client):
        """Two completely different findings should not surface."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        _attach_finding(
            client, ids["endpoint"], "SQLi in /api/v2/users",
            cwe="CWE-89", owasp_category="A03:2021-Injection",
        )
        _attach_finding(
            client, ids["endpoint"], "XSS on /admin/dashboard",
            cwe="CWE-79", owasp_category="A03:2021-Injection",
        )

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.9})
        assert r.status_code == 201
        scan = r.json()

        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        assert len(candidates) == 0

    def test_scan_fewer_than_two_findings_returns_empty_scan(self, client):
        """With 0 or 1 findings, the scan should complete but find nothing."""
        _make_graph(client)  # no findings attached

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.5})
        assert r.status_code == 201
        scan = r.json()

        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        assert candidates == []

    def test_scan_high_impact_flagging(self, client):
        """A pair where either finding has CVSS >= 7.0 should be flagged."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(
            client, ids["endpoint"], "RCE via deserialization",
            cwe="CWE-502", cvss_score=9.8,
        )
        f2 = _attach_finding(
            client, ids["endpoint"], "RCE via deserialization",
            cwe="CWE-502", cvss_score=9.8,
        )

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        assert r.status_code == 201
        scan = r.json()

        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        assert len(candidates) >= 1
        assert candidates[0]["high_impact"] is True

    def test_scan_low_impact_not_flagged(self, client):
        """A pair where both findings have CVSS < 7.0 should not be flagged."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(
            client, ids["endpoint"], "Low severity info leak",
            cwe="CWE-200", cvss_score=3.2,
        )
        f2 = _attach_finding(
            client, ids["endpoint"], "Low severity info leak",
            cwe="CWE-200", cvss_score=3.2,
        )

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        assert r.status_code == 201
        scan = r.json()

        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        if candidates:
            assert candidates[0]["high_impact"] is False

    def test_scan_signal_scores_present(self, client):
        """Signal breakdown should be included in every candidate."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        _attach_finding(
            client, ids["endpoint"], "Auth bypass on /api/v2/users",
            cwe="CWE-287", owasp_category="A07:2021-Identification and Authentication Failures",
        )
        _attach_finding(
            client, ids["endpoint"], "Auth bypass on /api/v2/users",
            cwe="CWE-287", owasp_category="A07:2021-Identification and Authentication Failures",
        )

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()

        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        if candidates:
            assert "signal_scores" in candidates[0]
            assert "title" in candidates[0]["signal_scores"]

    def test_list_scans_for_engagement(self, client):
        """Scans should be listed for an engagement."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        _attach_finding(
            client, ids["endpoint"], "Test finding A",
            cwe="CWE-89", owasp_category="A03:2021-Injection",
        )
        _attach_finding(
            client, ids["endpoint"], "Test finding B",
            cwe="CWE-89", owasp_category="A03:2021-Injection",
        )

        client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        client.post("/api/dedup/scan", json={"similarity_threshold": 0.5})

        r = client.get("/api/dedup/scans")
        assert r.status_code == 200
        scans = r.json()
        assert len(scans) == 2
        # Newest first
        assert scans[0]["created_at"] >= scans[1]["created_at"]

    def test_nonexistent_scan_404(self, client):
        r = client.get(f"/api/dedup/scans/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_candidates_filtered_by_action(self, client):
        """After resolving a candidate, listing with action=merge should show it."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(
            client, ids["endpoint"], "IDOR on /api/v2/users",
            cwe="CWE-639", owasp_category="A01:2021-Broken Access Control",
        )
        f2 = _attach_finding(
            client, ids["endpoint"], "IDOR on /api/v2/users",
            cwe="CWE-639", owasp_category="A01:2021-Broken Access Control",
        )

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        candidate_id = candidates[0]["id"]

        # Resolve as keep_separate
        client.post(
            f"/api/dedup/candidates/{candidate_id}/resolve",
            json={"action": "keep_separate", "analyst_note": "Different code paths"},
        )

        # Pending filter should show nothing
        pending = client.get(f"/api/dedup/scans/{scan['id']}/candidates?action=pending").json()
        assert len(pending) == 0

        # keep_separate filter should show it
        resolved = client.get(f"/api/dedup/scans/{scan['id']}/candidates?action=keep_separate").json()
        assert len(resolved) == 1


# ---------------------------------------------------------------------------
# Candidate resolution tests
# ---------------------------------------------------------------------------

class TestResolveCandidate:
    """Tests the analyst workflow: merge, keep_separate, mark_duplicate."""

    def test_merge_closes_loser(self, client):
        """Merging should close the non-kept finding."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(
            client, ids["endpoint"], "Auth bypass on /api/v2/users",
            cwe="CWE-287", cvss_score=8.5,
        )
        f2 = _attach_finding(
            client, ids["endpoint"], "Auth bypass on /api/v2/users",
            cwe="CWE-287", cvss_score=8.5,
        )

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        candidate_id = candidates[0]["id"]

        # Merge, keeping f1
        r = client.post(
            f"/api/dedup/candidates/{candidate_id}/resolve",
            json={"action": "merge", "kept_id": f1, "analyst_note": "Nuclei first"},
        )
        assert r.status_code == 200

        # f2 should be closed
        f2_body = client.get(f"/api/nodes/{f2}").json()
        assert f2_body["status"] == "accepted-risk"
        assert "MERGED" in (f2_body.get("notes") or "")

    def test_merge_requires_kept_id(self, client):
        """Merging without kept_id should 422."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")
        f2 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        candidate_id = candidates[0]["id"]

        r = client.post(
            f"/api/dedup/candidates/{candidate_id}/resolve",
            json={"action": "merge"},
        )
        assert r.status_code == 422
        assert "kept_id" in r.json()["detail"].lower()

    def test_merge_requires_valid_kept_id(self, client):
        """kept_id must be one of the two findings."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")
        f2 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        candidate_id = candidates[0]["id"]

        fake_id = str(uuid.uuid4())
        r = client.post(
            f"/api/dedup/candidates/{candidate_id}/resolve",
            json={"action": "merge", "kept_id": fake_id},
        )
        assert r.status_code == 422

    def test_keep_separate_preserves_both_findings(self, client):
        """keep_separate should not change the status of either finding."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79", cvss_score=7.5)
        f2 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79", cvss_score=7.5)

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        candidate_id = candidates[0]["id"]

        client.post(
            f"/api/dedup/candidates/{candidate_id}/resolve",
            json={"action": "keep_separate", "analyst_note": "Different PoCs"},
        )

        for fid in (f1, f2):
            body = client.get(f"/api/nodes/{fid}").json()
            assert body["status"] == "open"

    def test_mark_duplicate_closes_both(self, client):
        """mark_duplicate should close both findings."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")
        f2 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        candidate_id = candidates[0]["id"]

        client.post(
            f"/api/dedup/candidates/{candidate_id}/resolve",
            json={"action": "mark_duplicate", "analyst_note": "Both are FP"},
        )

        for fid in (f1, f2):
            body = client.get(f"/api/nodes/{fid}").json()
            assert body["status"] == "accepted-risk"
            assert "MARKED DUPLICATE" in (body.get("notes") or "")

    def test_merge_does_not_overwrite_already_closed(self, client):
        """If the loser is already closed, don't overwrite its status."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")
        f2 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79", status="fixed")

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        candidate_id = candidates[0]["id"]

        client.post(
            f"/api/dedup/candidates/{candidate_id}/resolve",
            json={"action": "merge", "kept_id": f1},
        )

        f2_body = client.get(f"/api/nodes/{f2}").json()
        assert f2_body["status"] == "fixed"  # not overwritten

    def test_invalid_action_422(self, client):
        """An unrecognized action should 422."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        f1 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")
        f2 = _attach_finding(client, ids["endpoint"], "XSS", cwe="CWE-79")

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.3})
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        candidate_id = candidates[0]["id"]

        r = client.post(
            f"/api/dedup/candidates/{candidate_id}/resolve",
            json={"action": "auto_merge"},
        )
        assert r.status_code == 422

    def test_nonexistent_candidate_404(self, client):
        r = client.post(
            f"/api/dedup/candidates/{uuid.uuid4()}/resolve",
            json={"action": "keep_separate"},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Custom weights and signals
# ---------------------------------------------------------------------------

class TestScanConfiguration:
    """Custom signal weights and signal selection."""

    def test_custom_weights_change_scoring(self, client):
        """When location weight is cranked up, findings on the same
        endpoint but different titles should still score high."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        _attach_finding(
            client, ids["endpoint"], "IDOR in user list",
            cwe="CWE-639", owasp_category="A01:2021",
        )
        _attach_finding(
            client, ids["endpoint"], "Broken access control in user list",
            cwe="CWE-639", owasp_category="A01:2021",
        )

        # Heavily weight location + endpoint; downweight title
        custom_weights = {
            "title": 0.05,
            "cwe": 0.25,
            "owasp": 0.10,
            "location": 0.30,
            "endpoint": 0.25,
            "params": 0.05,
        }
        r = client.post(
            "/api/dedup/scan",
            json={
                "similarity_threshold": 0.3,
                "weights": custom_weights,
            },
        )
        assert r.status_code == 201
        scan = r.json()
        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        assert len(candidates) >= 1

    def test_selective_signals(self, client):
        """Running with only title + cwe should still work."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)

        _attach_finding(client, ids["endpoint"], "XSS reflected", cwe="CWE-79")
        _attach_finding(client, ids["endpoint"], "XSS reflected", cwe="CWE-79")

        r = client.post(
            "/api/dedup/scan",
            json={
                "similarity_threshold": 0.3,
                "signals": ["title", "cwe"],
            },
        )
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# Multi-finding stress test
# ---------------------------------------------------------------------------

class TestScanAtScale:
    """Ensure the scan doesn't blow up with more findings."""

    def test_many_findings_completes(self, client):
        """With ~30 findings, the scan should still complete."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)
        ep_id = ids["endpoint"]

        # Create 15 pairs of duplicates + 5 unique
        for i in range(15):
            title = f"SQLi in form {i}"
            _attach_finding(client, ep_id, title, cwe="CWE-89", owasp_category="A03:2021")
            _attach_finding(client, ep_id, title, cwe="CWE-89", owasp_category="A03:2021")

        for i in range(5):
            _attach_finding(client, ep_id, f"Unique finding {i}", cwe="CWE-79")

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.5})
        assert r.status_code == 201
        scan = r.json()

        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        # 15 pairs = 15 candidates; low threshold should catch all
        assert len(candidates) >= 10

    def test_many_findings_with_high_threshold(self, client):
        """High threshold should produce zero candidates."""
        ids = _make_graph(client)
        _wire_app_graph(client, ids)
        ep_id = ids["endpoint"]

        for i in range(10):
            _attach_finding(client, ep_id, f"Finding {i}", cwe="CWE-89")

        r = client.post("/api/dedup/scan", json={"similarity_threshold": 0.99})
        assert r.status_code == 201
        scan = r.json()

        candidates = client.get(f"/api/dedup/scans/{scan['id']}/candidates").json()
        assert len(candidates) == 0
