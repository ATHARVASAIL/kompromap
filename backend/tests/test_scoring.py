import pytest

from app.models import Edge, EdgeType, Finding, NodeType
from app.services.scoring import DEFAULT_WEIGHTS, ScoringWeights, ease_score, edge_cost


def _finding(**kwargs) -> Finding:
    defaults = dict(
        node_type=NodeType.FINDING.value,
        title="Test finding",
        cvss_score=None,
        exploit_public=False,
        auth_required=True,
        status="open",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


def test_ease_score_maxes_out_for_critical_unauth_public_exploit():
    f = _finding(cvss_score=10.0, exploit_public=True, auth_required=False)
    # complexity term uses default_complexity=0.5, contributing 0.05 of the 0.1 weight
    score = ease_score(f)
    assert score == pytest.approx(0.4 + 0.3 + 0.2 + 0.05)


def test_ease_score_minimal_for_low_cvss_private_auth_required():
    f = _finding(cvss_score=0.0, exploit_public=False, auth_required=True)
    score = ease_score(f)
    assert score == pytest.approx(0.05)  # only the complexity term contributes


def test_ease_score_missing_cvss_treated_as_zero():
    f = _finding(cvss_score=None, exploit_public=False, auth_required=True)
    score = ease_score(f)
    assert score == pytest.approx(0.05)


def test_ease_score_is_bounded_0_to_1():
    f = _finding(cvss_score=10.0, exploit_public=True, auth_required=False)
    weird_weights = ScoringWeights(cvss=2.0, exploit_public=2.0, auth_required=2.0, complexity=2.0)
    score = ease_score(f, weird_weights)
    assert 0.0 <= score <= 1.0


def test_custom_default_complexity_changes_score():
    f = _finding(cvss_score=0.0, exploit_public=False, auth_required=True)
    low_complexity = ScoringWeights(default_complexity=0.0)  # "trivial" — full complexity credit
    score = ease_score(f, low_complexity)
    assert score == pytest.approx(0.1)  # complexity term now contributes its full weight


def test_scoring_weights_normalized():
    w = ScoringWeights(cvss=4, exploit_public=3, auth_required=2, complexity=1)
    n = w.normalized()
    assert abs((n.cvss + n.exploit_public + n.auth_required + n.complexity) - 1.0) < 1e-9
    assert n.cvss == 0.4


def test_edge_cost_yields_edge_from_finding_uses_ease_score():
    f = _finding(cvss_score=10.0, exploit_public=True, auth_required=False)
    edge = Edge(edge_type=EdgeType.YIELDS.value)
    cost = edge_cost(edge, f)
    assert cost == 1.0 - ease_score(f)


def test_edge_cost_structural_edge_defaults_to_zero():
    f = _finding(cvss_score=10.0, exploit_public=True, auth_required=False)
    edge = Edge(edge_type=EdgeType.HOSTS.value)
    assert edge_cost(edge, f) == 0.0


def test_edge_cost_manual_weight_overrides_computed_default():
    f = _finding(cvss_score=10.0, exploit_public=True, auth_required=False)
    edge = Edge(edge_type=EdgeType.YIELDS.value, weight=0.9)
    assert edge_cost(edge, f) == 1.0 - 0.9


def test_edge_cost_manual_weight_overrides_even_structural_edges():
    from app.models import Asset

    asset = Asset(node_type=NodeType.ASSET.value, name="x.com", asset_type="domain")
    edge = Edge(edge_type=EdgeType.HOSTS.value, weight=0.2)
    assert edge_cost(edge, asset) == 0.8
