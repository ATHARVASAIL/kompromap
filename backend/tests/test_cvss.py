"""CVSS vector parsing and its effect on scoring.

This closes the largest accuracy gap in path-finding: `complexity` was a
flat 0.5 for every finding, so a one-click unauthenticated RCE and a race
condition needing a MITM position scored identically on that term. Attack
Complexity is a real CVSS field, so when a vector is present we use it.

Getting this wrong doesn't throw — it just silently ranks the wrong attack
path first, which is the whole product. Hence the coverage.
"""
import pytest

from app.models import Finding, NodeType
from app.services.cvss import (
    ComplexityBasis,
    complexity_from_vector,
    parse_cvss_vector,
)
from app.services.scoring import DEFAULT_WEIGHTS, ScoringWeights, score_finding

LOG4SHELL = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
HARD = "CVSS:3.1/AV:N/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N"


def _finding(**kw) -> Finding:
    defaults = dict(
        node_type=NodeType.FINDING.value,
        title="t",
        cvss_score=None,
        cvss_vector=None,
        exploit_public=False,
        auth_required=True,
        status="open",
    )
    defaults.update(kw)
    return Finding(**defaults)


class TestVectorParsing:
    def test_parses_a_full_v31_vector(self):
        v = parse_cvss_vector(LOG4SHELL)
        assert v is not None
        assert v.attack_vector == "N"
        assert v.attack_complexity == "L"
        assert v.privileges_required == "N"
        assert v.user_interaction == "N"
        assert v.scope == "C"

    def test_parses_v30_as_well_as_v31(self):
        assert parse_cvss_vector("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is not None

    def test_rejects_cvss_v2(self):
        """v2 reuses AV:/AC: with different meanings — AC:M has no v3
        equivalent — so parsing one as v3 would be confidently wrong."""
        assert parse_cvss_vector("AV:N/AC:L/Au:N/C:P/I:P/A:P") is None

    @pytest.mark.parametrize("bad", ["", "garbage", "CVSS:4.0/AV:N", None, "AV:N/AC:L"])
    def test_rejects_anything_malformed(self, bad):
        assert parse_cvss_vector(bad) is None

    def test_tolerates_surrounding_whitespace(self):
        assert parse_cvss_vector(f"  {LOG4SHELL}  ") is not None

    def test_exposes_reachability_helpers(self):
        v = parse_cvss_vector(LOG4SHELL)
        assert v.is_network_reachable is True
        assert v.is_unauthenticated is True
        assert v.needs_user_interaction is False

        hard = parse_cvss_vector(HARD)
        assert hard.is_unauthenticated is False
        assert hard.needs_user_interaction is True


class TestComplexityDerivation:
    def test_trivial_exploit_scores_low_complexity(self):
        c, basis = complexity_from_vector(LOG4SHELL, default=0.5)
        assert basis is ComplexityBasis.VECTOR
        assert c < 0.2

    def test_hard_exploit_scores_high_complexity(self):
        c, basis = complexity_from_vector(HARD, default=0.5)
        assert basis is ComplexityBasis.VECTOR
        assert c > 0.7

    def test_falls_back_and_says_so_when_no_vector(self):
        c, basis = complexity_from_vector(None, default=0.42)
        assert c == 0.42
        assert basis is ComplexityBasis.DEFAULT

    def test_complexity_is_always_in_range(self):
        for vec in [LOG4SHELL, HARD, None, "junk"]:
            c, _ = complexity_from_vector(vec, default=0.5)
            assert 0.0 <= c <= 1.0

    def test_attack_complexity_dominates_the_blend(self):
        """AC is the metric CVSS defines as difficulty proper; PR and UI
        are preconditions and should matter less."""
        only_ac_easy, _ = complexity_from_vector("CVSS:3.1/AV:N/AC:L/PR:H/UI:N", 0.5)
        only_ac_hard, _ = complexity_from_vector("CVSS:3.1/AV:N/AC:H/PR:N/UI:N", 0.5)
        assert only_ac_hard > only_ac_easy


class TestScoringWithVectors:
    def test_trivial_exploit_outscores_hard_one_with_same_cvss(self):
        """Same numeric CVSS, opposite complexity — the whole point of
        parsing the vector. Previously these scored identically."""
        easy = score_finding(_finding(cvss_score=9.0, cvss_vector=LOG4SHELL))
        hard = score_finding(_finding(cvss_score=9.0, cvss_vector=HARD))
        assert easy.ease_score > hard.ease_score

    def test_reports_whether_complexity_was_measured_or_assumed(self):
        assert score_finding(_finding(cvss_vector=LOG4SHELL)).complexity_is_measured is True
        assert score_finding(_finding(cvss_vector=None)).complexity_is_measured is False

    def test_vector_privileges_override_the_auth_required_boolean(self):
        """PR:N means genuinely unauthenticated even if the coarse boolean
        says otherwise — the vector is the better source."""
        b = score_finding(_finding(cvss_vector=LOG4SHELL, auth_required=True))
        assert b.unauthenticated == 1.0

    def test_falls_back_to_auth_required_without_a_vector(self):
        assert score_finding(_finding(auth_required=False)).unauthenticated == 1.0
        assert score_finding(_finding(auth_required=True)).unauthenticated == 0.0

    def test_contributions_sum_to_the_total(self):
        b = score_finding(_finding(cvss_score=8.0, cvss_vector=LOG4SHELL, exploit_public=True))
        assert sum(b.contributions.values()) == pytest.approx(b.ease_score)

    def test_breakdown_names_every_weighted_term(self):
        b = score_finding(_finding(cvss_score=5.0))
        assert set(b.contributions) == {"cvss", "exploit_public", "unauthenticated", "complexity"}

    def test_score_stays_in_range_under_absurd_weights(self):
        weights = ScoringWeights(cvss=99, exploit_public=99, auth_required=99, complexity=99)
        b = score_finding(_finding(cvss_score=10, cvss_vector=LOG4SHELL, exploit_public=True), weights)
        assert 0.0 <= b.ease_score <= 1.0

    def test_default_weights_still_produce_the_spec_formula(self):
        """Regression guard: the spec's 0.4/0.3/0.2/0.1 split must survive."""
        b = score_finding(
            _finding(cvss_score=10.0, exploit_public=True, auth_required=False), DEFAULT_WEIGHTS
        )
        assert b.contributions["cvss"] == pytest.approx(0.4)
        assert b.contributions["exploit_public"] == pytest.approx(0.3)
        assert b.contributions["unauthenticated"] == pytest.approx(0.2)
