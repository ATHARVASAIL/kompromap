"""Tests for the correlation / extended risk service (Phase 3)."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models import Asset, Edge, Endpoint, Engagement, Finding, Node, WebApplication
from app.models.edge import EdgeType
from app.models.enums import NodeType
from app.services.correlation import (
    _criticality_score,
    _data_sensitivity_score,
    compute_asset_risk,
    compute_correlation_matrix,
)


def _make_engagement(db: Session) -> Engagement:
    eng = Engagement(name="corr-test", active=True)
    db.add(eng)
    db.flush()
    return eng


def _make_asset(db: Session, eng_id: uuid.UUID, name: str, asset_type: str = "domain", tags: list[str] | None = None) -> Asset:
    node = Node(node_type=NodeType.ASSET.value, engagement_id=eng_id)
    db.add(node)
    db.flush()
    asset = Asset(id=node.id, name=name, asset_type=asset_type, in_scope=True, tags=tags or [])
    db.add(asset)
    db.flush()
    return asset


def _make_finding(
    db: Session, eng_id: uuid.UUID, asset: Asset,
    title: str, cwe: str | None = None, cvss_score: float | None = 5.0,
) -> Finding:
    node = Node(node_type=NodeType.FINDING.value, engagement_id=eng_id)
    db.add(node)
    db.flush()
    f = Finding(id=node.id, title=title, cwe=cwe, cvss_score=cvss_score,
                exploit_public=False, evidence="")
    db.add(f)
    db.flush()
    db.add(Edge(source_node_id=asset.id, target_node_id=f.id, edge_type=EdgeType.HAS_FINDING.value))
    db.flush()
    return f


class TestCriticalityScore:
    def test_crown_jewel_is_max(self, db_session):
        asset = _make_asset(db_session, uuid.uuid4(), "cj.example.com", tags=["crown-jewel"])
        assert _criticality_score(asset) == pytest.approx(1.0)

    def test_production_tag(self, db_session):
        asset = _make_asset(db_session, uuid.uuid4(), "prod.example.com", tags=["production"])
        assert _criticality_score(asset) == pytest.approx(0.8)

    def test_fallback_on_type(self, db_session):
        asset = _make_asset(db_session, uuid.uuid4(), "db.example.com", asset_type="database")
        assert _criticality_score(asset) == pytest.approx(0.9)

    def test_unknown_defaults(self, db_session):
        asset = _make_asset(db_session, uuid.uuid4(), "x.example.com", asset_type="unknown")
        assert _criticality_score(asset) == pytest.approx(0.5)


class TestDataSensitivityScore:
    def test_pci_is_high(self, db_session):
        asset = _make_asset(db_session, uuid.uuid4(), "pay.example.com", tags=["pci"])
        assert _data_sensitivity_score(asset) == pytest.approx(0.95)

    def test_public_is_low(self, db_session):
        asset = _make_asset(db_session, uuid.uuid4(), "blog.example.com", tags=["public"])
        assert _data_sensitivity_score(asset) == pytest.approx(0.1)

    def test_from_notes(self, db_session):
        asset = _make_asset(db_session, uuid.uuid4(), "x.example.com", tags=[])
        asset.notes = "handles PII data"
        assert _data_sensitivity_score(asset) == pytest.approx(0.9)


class TestComputeAssetRisk:
    def test_no_findings_zero_risk(self, db_session):
        eng = _make_engagement(db_session)
        _make_asset(db_session, eng.id, "clean.example.com")
        risks = compute_asset_risk(db_session, eng.id)
        assert len(risks) == 1
        assert risks[0].extended_risk == 0.0

    def test_high_cvss_high_risk(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "critical.example.com", tags=["crown-jewel", "pci"])
        _make_finding(db_session, eng.id, asset, "RCE", cwe="CWE-78", cvss_score=9.5)
        risks = compute_asset_risk(db_session, eng.id)
        assert len(risks) == 1
        r = risks[0]
        assert r.extended_risk > 0
        assert r.critical_findings == 1
        assert r.base_cvss == pytest.approx(9.5)

    def test_sorted_by_extended_risk(self, db_session):
        eng = _make_engagement(db_session)
        a1 = _make_asset(db_session, eng.id, "low.example.com")
        a2 = _make_asset(db_session, eng.id, "high.example.com", tags=["crown-jewel"])
        _make_finding(db_session, eng.id, a1, "Low", cvss_score=3.0)
        _make_finding(db_session, eng.id, a2, "High", cvss_score=9.0)
        risks = compute_asset_risk(db_session, eng.id)
        assert risks[0].asset_name == "high.example.com"

    def test_cwe_grouping(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "app.example.com")
        _make_finding(db_session, eng.id, asset, "XSS 1", cwe="CWE-79", cvss_score=4.0)
        _make_finding(db_session, eng.id, asset, "XSS 2", cwe="CWE-79", cvss_score=5.0)
        _make_finding(db_session, eng.id, asset, "SQLi", cwe="CWE-89", cvss_score=7.0)
        result = compute_correlation_matrix(db_session, eng.id)
        assert result["total_findings"] == 3
        assert result["unique_cwes"] == 2


class TestExposureScore:
    def test_no_edges_no_exposure(self, db_session):
        eng = _make_engagement(db_session)
        asset = _make_asset(db_session, eng.id, "isolated.example.com")
        risks = compute_asset_risk(db_session, eng.id)
        assert risks[0].exposure == 0.0
        assert risks[0].attack_paths_in == 0
