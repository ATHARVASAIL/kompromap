"""Tests for the deduplication engine (Phase 2)."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models import Asset, Edge, Endpoint, Engagement, Finding, Node
from app.models.dedup import DedupScan, MergeCandidate
from app.models.edge import EdgeType
from app.models.enums import NodeType
from app.services.dedup import (
    DEFAULT_OVERALL_THRESHOLD,
    DIMENSION_WEIGHTS,
    HIGH_CONFIDENCE_THRESHOLD,
    HIGH_IMPACT_CVSS,
    composite_score,
    get_candidates,
    get_latest_scan,
    run_dedup_scan,
    score_dimensions,
)


def _make_engagement(db: Session) -> Engagement:
    eng = Engagement(name="dedup-test", active=True)
    db.add(eng)
    db.flush()
    return eng


def _make_asset(db: Session, eng_id: uuid.UUID, name: str, tags: list[str] | None = None) -> Asset:
    node = Node(node_type=NodeType.ASSET.value, engagement_id=eng_id)
    db.add(node)
    db.flush()
    asset = Asset(id=node.id, name=name, asset_type="domain", in_scope=True, tags=tags or [])
    db.add(asset)
    db.flush()
    return asset


def _make_finding(
    db: Session,
    eng_id: uuid.UUID,
    asset: Asset,
    title: str,
    cwe: str | None = None,
    cvss_score: float | None = 5.0,
    exploit_public: bool = False,
    evidence: str | None = "",
) -> Finding:
    node = Node(node_type=NodeType.FINDING.value, engagement_id=eng_id)
    db.add(node)
    db.flush()
    f = Finding(
        id=node.id,
        title=title,
        cwe=cwe,
        cvss_score=cvss_score,
        exploit_public=exploit_public,
        evidence=evidence or "",
    )
    db.add(f)
    db.flush()
    # HAS_FINDING edge from asset -> finding
    edge = Edge(
        source_node_id=asset.id,
        target_node_id=f.id,
        edge_type=EdgeType.HAS_FINDING.value,
    )
    db.add(edge)
    db.flush()
    return f


# ── Dimension / composite scoring ──────────────────────────────────────────

class TestScoreDimensions:
    def test_identical_findings_score_1(self):
        from app.services.dedup import FindingContext
        a = FindingContext(finding_id=uuid.uuid4(), title="XSS", cwe="CWE-79", cvss_score=5.0,
                           exploit_public=False, evidence="", endpoint_path="/api",
                           endpoint_method="GET", endpoint_params=["id"], asset_name="app",
                           asset_tags=["web"], url="https://app.com/api")
        b = FindingContext(finding_id=uuid.uuid4(), title="XSS", cwe="CWE-79", cvss_score=5.0,
                           exploit_public=False, evidence="", endpoint_path="/api",
                           endpoint_method="GET", endpoint_params=["id"], asset_name="app",
                           asset_tags=["web"], url="https://app.com/api")
        dims = score_dimensions(a, b)
        assert dims["endpoint_similarity"] == 1.0
        assert dims["cwe_similarity"] == 1.0
        assert dims["param_similarity"] == 1.0

    def test_different_cwes_zero(self):
        from app.services.dedup import FindingContext
        a = FindingContext(finding_id=uuid.uuid4(), title="XSS", cwe="CWE-79", cvss_score=5.0,
                           exploit_public=False, evidence="", endpoint_path=None, endpoint_method=None,
                           endpoint_params=[], asset_name="a", asset_tags=[], url=None)
        b = FindingContext(finding_id=uuid.uuid4(), title="SQLi", cwe="CWE-89", cvss_score=5.0,
                           exploit_public=False, evidence="", endpoint_path=None, endpoint_method=None,
                           endpoint_params=[], asset_name="a", asset_tags=[], url=None)
        dims = score_dimensions(a, b)
        assert dims["cwe_similarity"] == 0.0

    def test_composite_score_weights(self):
        dims = {
            "url_similarity": 1.0,
            "endpoint_similarity": 1.0,
            "param_similarity": 1.0,
            "cwe_similarity": 1.0,
            "request_similarity": 1.0,
            "response_similarity": 1.0,
        }
        assert composite_score(dims) == pytest.approx(1.0)

    def test_composite_score_weights_sum_correctly(self):
        dims = {
            "url_similarity": 0.5,
            "endpoint_similarity": 0.5,
            "param_similarity": 0.5,
            "cwe_similarity": 0.5,
            "request_similarity": 0.5,
            "response_similarity": 0.5,
        }
        assert composite_score(dims) == pytest.approx(0.5)

    def test_high_impact_never_candidates(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "critical.example.com")
        f1 = _make_finding(db_session, eng.id, asset, "RCE", cwe="CWE-78",
                           cvss_score=9.5, exploit_public=True)
        f2 = _make_finding(db_session, eng.id, asset, "RCE dup", cwe="CWE-78",
                           cvss_score=5.0, exploit_public=False)
        # Same everything — but f1 is high-impact (CVSS >= 7)
        scan = run_dedup_scan(db_session, eng.id, threshold=0.5)
        assert scan.total_candidates == 0


class TestDedupScan:
    def test_full_scan_creates_candidates(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "app.example.com")
        f1 = _make_finding(db_session, eng.id, asset, "XSS /search",
                           cwe="CWE-79", cvss_score=5.0,
                           evidence='{"url":"https://app.com/search?q=1"}')
        f2 = _make_finding(db_session, eng.id, asset, "XSS /search",
                           cwe="CWE-79", cvss_score=5.0,
                           evidence='{"url":"https://app.com/search?q=2"}')
        # Also attach endpoints so endpoint_similarity is meaningful
        n1 = Node(node_type=NodeType.ENDPOINT.value, engagement_id=eng.id)
        n2 = Node(node_type=NodeType.ENDPOINT.value, engagement_id=eng.id)
        db_session.add_all([n1, n2])
        db_session.flush()
        ep1 = Endpoint(id=n1.id, node_type=NodeType.ENDPOINT.value, engagement_id=eng.id,
                       asset_id=asset.id, path="/search", params=["q"], requires_auth=False)
        ep2 = Endpoint(id=n2.id, node_type=NodeType.ENDPOINT.value, engagement_id=eng.id,
                       asset_id=asset.id, path="/search", params=["q"], requires_auth=False)
        db_session.add_all([ep1, ep2])
        db_session.flush()
        db_session.add_all([
            Edge(source_node_id=ep1.id, target_node_id=f1.id, edge_type=EdgeType.EXPOSES.value),
            Edge(source_node_id=ep2.id, target_node_id=f2.id, edge_type=EdgeType.EXPOSES.value),
        ])
        db_session.flush()

        scan = run_dedup_scan(db_session, eng.id, threshold=0.5)
        assert scan.total_candidates >= 1
        assert scan.id is not None

    def test_no_duplicates_empty(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "unique.example.com")
        _make_finding(db_session, eng.id, asset, "Unique finding A")
        _make_finding(db_session, eng.id, asset, "Unique finding B", cwe="CWE-99")
        scan = run_dedup_scan(db_session, eng.id, threshold=0.9)
        assert scan.total_candidates == 0

    def test_get_latest_scan(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "scan.example.com")
        _make_finding(db_session, eng.id, asset, "F1")
        _make_finding(db_session, eng.id, asset, "F2", cwe="CWE-1")
        run_dedup_scan(db_session, eng.id)
        run_dedup_scan(db_session, eng.id)
        latest = get_latest_scan(db_session, eng.id)
        assert latest is not None


class TestResolveCandidate:
    def test_merge_action(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "resolve.example.com")
        f1 = _make_finding(db_session, eng.id, asset, "Keep me", cvss_score=5.0)
        f2 = _make_finding(db_session, eng.id, asset, "Merge me", cvss_score=5.0)
        candidate = MergeCandidate(
            scan_id=uuid.uuid4(), engagement_id=eng.id,
            finding_a_id=f1.id, finding_b_id=f2.id,
            url_similarity=0.9, endpoint_similarity=0.9, param_similarity=1.0,
            cwe_similarity=1.0, request_similarity=0.8, response_similarity=0.8,
            overall_score=0.9, threshold_used=0.75, status="pending",
        )
        db_session.add(candidate)
        db_session.flush()
        resolved = run_dedup_scan.__module__  # use service directly
        from app.services.dedup import resolve_candidate
        result = resolve_candidate(db_session, candidate.id, "merged", "same vuln")
        assert result.status == "merged"
        assert result.resolved_at is not None

    def test_dismiss_action(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "dismiss.example.com")
        f1 = _make_finding(db_session, eng.id, asset, "F1", cvss_score=5.0)
        f2 = _make_finding(db_session, eng.id, asset, "F2", cwe="CWE-1", cvss_score=5.0)
        candidate = MergeCandidate(
            scan_id=uuid.uuid4(), engagement_id=eng.id,
            finding_a_id=f1.id, finding_b_id=f2.id,
            url_similarity=0.8, endpoint_similarity=0.8, param_similarity=1.0,
            cwe_similarity=0.0, request_similarity=0.5, response_similarity=0.5,
            overall_score=0.7, threshold_used=0.75, status="pending",
        )
        db_session.add(candidate)
        db_session.flush()
        from app.services.dedup import resolve_candidate
        result = resolve_candidate(db_session, candidate.id, "dismissed", "different vulns")
        assert result.status == "dismissed"
