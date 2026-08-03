"""Ease-score scoring per spec §4:

    ease_score = normalize(cvss_score) * 0.4
               + exploit_public_availability * 0.3
               + (1 - auth_required) * 0.2
               + (1 - complexity) * 0.1

    cost = 1 - ease_score

Data gap, worth being explicit about: `complexity` appears in the formula
but isn't a stored property anywhere in the Finding schema (spec §4's
property table only lists cvss_score, exploit_public, auth_required — no
complexity field). Rather than invent a value and present it as real data,
this uses a configurable `default_complexity` (0.5 = neutral) applied
uniformly to every finding. Callers who want it to stop influencing the
score entirely can set the `complexity` weight to 0 in ScoringWeights.

Only YIELDS edges (Finding -> Credential/Account/DataStore, per spec §4's
edge table) get a computed ease_score — that's the one edge type the spec
frames as "exploiting this finding gets you this," i.e. an actual
exploitation step with a real cost. Every other edge type (HOSTS, EXPOSES,
HAS_FINDING, TRUSTS, AUTHENTICATES_AS, GRANTS_ACCESS_TO) represents an
already-established structural relationship or discovery, not an
exploitation action, so it defaults to zero cost (ease_score 1.0) unless
the tester manually set a weight on that specific edge — manual overrides
always win over the computed default.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models import Edge, EdgeType, Finding, Node
from app.services.cvss import ComplexityBasis, complexity_from_vector, parse_cvss_vector

# Edge type where the spec's ease_score formula actually applies.
EXPLOIT_EDGE_TYPE = EdgeType.YIELDS


@dataclass(frozen=True)
class ScoringWeights:
    cvss: float = 0.4
    exploit_public: float = 0.3
    auth_required: float = 0.2
    complexity: float = 0.1
    default_complexity: float = 0.5  # see module docstring

    def normalized(self) -> "ScoringWeights":
        """Weights that don't sum to 1.0 still produce a valid (if
        differently-scaled) ease_score — Dijkstra only cares about relative
        ordering, so this is a convenience, not a hard requirement."""
        total = self.cvss + self.exploit_public + self.auth_required + self.complexity
        if total <= 0:
            return self
        return ScoringWeights(
            cvss=self.cvss / total,
            exploit_public=self.exploit_public / total,
            auth_required=self.auth_required / total,
            complexity=self.complexity / total,
            default_complexity=self.default_complexity,
        )


DEFAULT_WEIGHTS = ScoringWeights()


@dataclass(frozen=True)
class ScoreBreakdown:
    """A scored finding, with every term shown separately.

    Path-finding used to surface a single opaque cost, which made it
    impossible to answer "why is this chain ranked above that one?" —
    the most obvious question a tester would ask. Returning the terms lets
    the UI show the reasoning.
    """

    ease_score: float
    normalized_cvss: float
    exploit_public: float
    unauthenticated: float
    complexity: float
    complexity_basis: ComplexityBasis
    # Per-term contributions after weighting — these sum to ease_score.
    contributions: dict[str, float]

    @property
    def complexity_is_measured(self) -> bool:
        """True when complexity came from a real CVSS vector rather than
        the configured fallback. The UI shows measured and assumed values
        differently — presenting both with equal confidence would be
        misleading."""
        return self.complexity_basis is ComplexityBasis.VECTOR


def score_finding(
    finding: Finding, weights: ScoringWeights = DEFAULT_WEIGHTS
) -> ScoreBreakdown:
    """Full ease_score computation with its terms exposed."""
    normalized_cvss = min(max((finding.cvss_score or 0.0) / 10.0, 0.0), 1.0)
    exploit_public_term = 1.0 if finding.exploit_public else 0.0

    # Prefer the CVSS vector's Privileges Required over the coarser
    # auth_required boolean when we have it — PR:N/PR:L/PR:H distinguishes
    # "no login", "any user" and "admin", which auth_required flattens.
    parsed = parse_cvss_vector(getattr(finding, "cvss_vector", None))
    if parsed is not None and parsed.privileges_required:
        unauth_term = 1.0 if parsed.is_unauthenticated else 0.0
    else:
        unauth_term = 0.0 if finding.auth_required else 1.0

    complexity, basis = complexity_from_vector(
        getattr(finding, "cvss_vector", None), weights.default_complexity
    )
    # The formula credits *ease*, so invert: low complexity -> high score.
    complexity_term = 1.0 - complexity

    contributions = {
        "cvss": normalized_cvss * weights.cvss,
        "exploit_public": exploit_public_term * weights.exploit_public,
        "unauthenticated": unauth_term * weights.auth_required,
        "complexity": complexity_term * weights.complexity,
    }
    total = max(0.0, min(1.0, sum(contributions.values())))

    return ScoreBreakdown(
        ease_score=total,
        normalized_cvss=normalized_cvss,
        exploit_public=exploit_public_term,
        unauthenticated=unauth_term,
        complexity=complexity,
        complexity_basis=basis,
        contributions=contributions,
    )


def ease_score(finding: Finding, weights: ScoringWeights = DEFAULT_WEIGHTS) -> float:
    """Just the number. Kept as the simple entry point for path-finding —
    score_finding() is for anything that needs to explain itself."""
    return score_finding(finding, weights).ease_score


def edge_cost(edge: Edge, source_node: Node, weights: ScoringWeights = DEFAULT_WEIGHTS) -> float:
    """Dijkstra edge weight — lower cost = easier/more realistic step.

    Manual overrides (edge.weight already set, e.g. from the "+ edge" UI
    form or a prior recompute) always take precedence over the computed
    default, on any edge type.
    """
    if edge.weight is not None:
        return 1.0 - edge.weight

    if EdgeType(edge.edge_type) == EXPLOIT_EDGE_TYPE and isinstance(source_node, Finding):
        return 1.0 - ease_score(source_node, weights)

    return 0.0  # structural edge, no computed cost — see module docstring
