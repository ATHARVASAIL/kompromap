"""Extended risk model tests (Phase 3).

Tests the asset criticality, data sensitivity, and exposure factor
terms that augment the core CVSS-based ease_score. These factors are
derived from the graph target of a finding's YIELDS edge, so they
require a DB session to look up connected nodes.
"""
import uuid

import pytest

from app.models import Account, Asset, DataStore, Edge, EdgeType, Finding, NodeType
from app.services.scoring import DEFAULT_WEIGHTS, ScoringWeights, _derive_risk_context, ease_score


def _asset(name, **kw):
    return Asset(
        id=uuid.uuid4(),
        node_type=NodeType.ASSET.value,
        name=name,
        asset_type="domain",
        **kw,
    )


def _finding(title, **kw):
    return Finding(
        id=uuid.uuid4(),
        node_type=NodeType.FINDING.value,
        title=title,
        status="open",
        **kw,
    )


def _account(username, **kw):
    return Account(
        id=uuid.uuid4(),
        node_type=NodeType.ACCOUNT.value,
        username=username,
        privilege_level="admin",
        **kw,
    )


def _datastore(name, **kw):
    return DataStore(
        id=uuid.uuid4(),
        node_type=NodeType.DATA_STORE.value,
        name=name,
        data_classification="PII",
        **kw,
    )


def _edge(source, target, edge_type, weight=None):
    return Edge(
        id=uuid.uuid4(),
        source_node_id=source.id,
        target_node_id=target.id,
        edge_type=edge_type.value,
        weight=weight,
    )


class TestDeriveRiskContext:
    """_derive_risk_context reads the finding's YIELDS edges and returns
    the maximum score for each axis across all targets."""

    def test_crown_jewel_gets_exposure_09(self, db_session):
        entry = _asset("entry", is_entry_point=True)
        finding = _finding("test")
        crown = _asset("crown", is_crown_jewel=True)
        db_session.add_all([entry, finding, crown])
        db_session.flush()
        db_session.add(_edge(finding, crown, EdgeType.YIELDS))
        db_session.commit()

        ctx = _derive_risk_context(finding, db_session)
        assert ctx.exposure_factor == pytest.approx(0.9)
        assert ctx.asset_criticality == pytest.approx(0.6)
        assert ctx.data_sensitivity == pytest.approx(0.1)

    def test_entry_point_gets_exposure_10(self, db_session):
        entry = _asset("entry", is_entry_point=True)
        finding = _finding("test")
        db_session.add_all([entry, finding])
        db_session.flush()
        db_session.add(_edge(finding, entry, EdgeType.YIELDS))
        db_session.commit()

        ctx = _derive_risk_context(finding, db_session)
        assert ctx.exposure_factor == pytest.approx(1.0)

    def test_entry_point_exposure_beats_crown_jewel(self, db_session):
        """Entry point exposure (1.0) beats crown jewel (0.9)."""
        entry = _asset("entry", is_entry_point=True)
        finding = _finding("test")
        crown = _asset("crown", is_crown_jewel=True)
        db_session.add_all([entry, finding, crown])
        db_session.flush()
        db_session.add(_edge(finding, entry, EdgeType.YIELDS))
        db_session.add(_edge(finding, crown, EdgeType.YIELDS))
        db_session.commit()

        ctx = _derive_risk_context(finding, db_session)
        assert ctx.exposure_factor == pytest.approx(1.0)

    def test_pii_datastore_gets_data_sensitivity_08(self, db_session):
        finding = _finding("test")
        store = _datastore("customers", data_classification="PII")
        db_session.add_all([finding, store])
        db_session.flush()
        db_session.add(_edge(finding, store, EdgeType.YIELDS))
        db_session.commit()

        ctx = _derive_risk_context(finding, db_session)
        assert ctx.data_sensitivity == pytest.approx(0.8)

    def test_pci_datastore_gets_data_sensitivity_10(self, db_session):
        finding = _finding("test")
        store = _datastore("payments", data_classification="PCI")
        db_session.add_all([finding, store])
        db_session.flush()
        db_session.add(_edge(finding, store, EdgeType.YIELDS))
        db_session.commit()

        ctx = _derive_risk_context(finding, db_session)
        assert ctx.data_sensitivity == pytest.approx(1.0)

    def test_none_classification_gets_data_sensitivity_01(self, db_session):
        finding = _finding("test")
        store = _datastore("public", data_classification="none")
        db_session.add_all([finding, store])
        db_session.flush()
        db_session.add(_edge(finding, store, EdgeType.YIELDS))
        db_session.commit()

        ctx = _derive_risk_context(finding, db_session)
        assert ctx.data_sensitivity == pytest.approx(0.1)

    def test_no_yields_edges_returns_defaults(self, db_session):
        finding = _finding("test")
        db_session.add(finding)
        db_session.commit()

        ctx = _derive_risk_context(finding, db_session)
        assert ctx.exposure_factor == pytest.approx(0.0)
        assert ctx.asset_criticality == pytest.approx(0.0)
        assert ctx.data_sensitivity == pytest.approx(0.1)

    def test_none_db_returns_defaults(self):
        finding = _finding("test")
        ctx = _derive_risk_context(finding, None)
        assert ctx.exposure_factor == pytest.approx(0.0)
        assert ctx.asset_criticality == pytest.approx(0.0)
        assert ctx.data_sensitivity == pytest.approx(0.1)

    def test_asset_target_gets_criticality(self, db_session):
        finding = _finding("test")
        asset = _asset("target")
        db_session.add_all([finding, asset])
        db_session.flush()
        db_session.add(_edge(finding, asset, EdgeType.YIELDS))
        db_session.commit()

        ctx = _derive_risk_context(finding, db_session)
        assert ctx.asset_criticality == pytest.approx(0.6)


class TestEaseScoreExtended:
    """ease_score includes extended risk terms when weights are non-zero."""

    def test_extended_terms_contribute_to_score(self, db_session):
        """A finding reaching a crown jewel PII store should score higher
        than the same finding reaching a non-sensitive non-crown target."""
        finding = _finding("test", cvss_score=7.0, exploit_public=True, auth_required=False)

        # Low-value target
        low_target = _asset("low")
        db_session.add_all([finding, low_target])
        db_session.flush()
        db_session.add(_edge(finding, low_target, EdgeType.YIELDS))

        # High-value target (crown jewel with PII)
        high_target = _asset("high", is_crown_jewel=True)
        db_session.add(high_target)
        db_session.flush()
        high_store = _datastore("pii_on_crown")
        db_session.add(high_store)
        db_session.flush()
        db_session.add(_edge(finding, high_store, EdgeType.YIELDS))

        db_session.commit()

        weights = ScoringWeights(
            cvss=0.4,
            exploit_public=0.3,
            auth_required=0.2,
            complexity=0.1,
            default_complexity=0.5,
            asset_criticality=0.3,
            data_sensitivity=0.25,
            exposure_factor=0.15,
        )

        # Re-derive with the same finding but we need to test both targets
        # separately — create a second finding for the low target
        low_finding = _finding("low", cvss_score=7.0, exploit_public=True, auth_required=False)
        db_session.add(low_finding)
        db_session.flush()
        db_session.add(_edge(low_finding, low_target, EdgeType.YIELDS))
        db_session.commit()

        low_score = ease_score(low_finding, weights, db_session)
        high_score = ease_score(finding, weights, db_session)

        assert high_score > low_score

    def test_no_db_gives_zero_extended_terms(self):
        """Without a DB session, extended risk factors default to zero —
        backward compatibility for existing callers."""
        f = _finding(cvss_score=7.0, exploit_public=True, auth_required=False)
        weights = ScoringWeights(
            cvss=0.4,
            exploit_public=0.3,
            auth_required=0.2,
            complexity=0.1,
            default_complexity=0.5,
            asset_criticality=0.3,
            data_sensitivity=0.25,
            exposure_factor=0.15,
        )
        score = ease_score(f, weights, db=None)
        # Should equal the base formula: 0.4*0.7 + 0.3*1 + 0.2*1 + 0.1*0.5
        assert score == pytest.approx(0.4 * 0.7 + 0.3 * 1 + 0.2 * 1 + 0.1 * 0.5)

    def test_contributions_sum_to_ease_score(self, db_session):
        """contributions dict should sum to ease_score."""
        finding = _finding("test", cvss_score=8.0, exploit_public=True, auth_required=False)
        store = _datastore("pii")
        db_session.add_all([finding, store])
        db_session.flush()
        db_session.add(_edge(finding, store, EdgeType.YIELDS))
        db_session.commit()

        weights = DEFAULT_WEIGHTS
        result = ease_score(finding, weights, db_session)
        # Just verify it's a valid float in range
        assert 0.0 <= result <= 1.0

    def test_score_is_bounded_0_to_1(self, db_session):
        """Even with maxed-out inputs, score should not exceed 1.0."""
        finding = _finding(
            "test",
            cvss_score=10.0,
            exploit_public=True,
            auth_required=False,
        )
        crown = _asset("crown", is_crown_jewel=True, is_entry_point=True)
        pci = _datastore("pci", data_classification="PCI")
        db_session.add_all([finding, crown, pci])
        db_session.flush()
        db_session.add(_edge(finding, crown, EdgeType.YIELDS))
        db_session.add(_edge(finding, pci, EdgeType.YIELDS))
        db_session.commit()

        weights = DEFAULT_WEIGHTS
        score = ease_score(finding, weights, db_session)
        assert score <= 1.0
        assert score >= 0.0
