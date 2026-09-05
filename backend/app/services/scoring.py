"""Ease-score scoring with extended risk factors (Phase 3):

    ease_score = normalize(cvss_score) * cvss_w
               + exploit_public_availability * exploit_w
               + (1 - auth_required) * auth_w
               + (1 - complexity) * complexity_w
               + asset_criticality * criticality_w
               + data_sensitivity * sensitivity_w
               + exposure_factor * exposure_w

    cost = 1 - ease_score

The extended factors are derived from the attack target node (DataStore,
Asset) rather than the finding itself, because risk is contextual:
a finding on a crown jewel with PII is more impactful than the same
finding on a test server. The scorer walks YIELDS edges from the
finding to its targets and aggregates the highest-risk context it can
reach.

Complexity note: `complexity` isn't a stored property anywhere in the
Finding schema (spec §4's property table only lists cvss_score,
exploit_public, auth_required — no complexity field). Rather than invent
a value and present it as real data, this uses a configurable
`default_complexity` (0.5 = neutral) applied uniformly to every
finding. Callers who want it to stop influencing the score entirely can
set the `complexity` weight to 0 in ScoringWeights.

Only YIELDS edges (Finding -> Credential/Account/DataStore, per spec §4's
edge table) get a computed ease_score — that's the one edge type the spec
frames as "exploiting this finding gets you this," i.e. an actual
exploitation step with a real cost. Every other edge type (HOSTS,
EXPOSES, HAS_FINDING, TRUSTS, AUTHENTICATES_AS, GRANTS_ACCESS_TO)
represents an already-established structural relationship or discovery,
not an exploitation action, so it defaults to zero cost (ease_score 1.0)
unless the tester manually set a weight on that specific edge — manual
overrides always win over the computed default.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.models import Edge, EdgeType, Finding, Node
from app.models.enums import DataClassification
from app.services.cvss import ComplexityBasis, complexity_from_vector, parse_cvss_vector

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Edge type where the spec's ease_score formula actually applies.
EXPLOIT_EDGE_TYPE = EdgeType.YIELDS


@dataclass(frozen=True)
class ScoringWeights:
    cvss: float = 0.4
    exploit_public: float = 0.3
    auth_required: float = 0.2
    complexity: float = 0.1
    default_complexity: float = 0.5  # see module docstring
    asset_criticality: float = 0.3
    data_sensitivity: float = 0.25
    exposure_factor: float = 0.15

    def normalized(self) -> "ScoringWeights":
        """Weights that don't sum to 1.0 still produce a valid (if
        differently-scaled) ease_score — Dijkstra only cares about relative
        ordering, so this is a convenience, not a hard requirement."""
        base = (
            self.cvss
            + self.exploit_public
            + self.auth_required
            + self.complexity
            + self.asset_criticality
            + self.data_sensitivity
            + self.exposure_factor
        )
        if base <= 0:
            return self
        return ScoringWeights(
            cvss=self.cvss / base,
            exploit_public=self.exploit_public / base,
            auth_required=self.auth_required / base,
            complexity=self.complexity / base,
            default_complexity=self.default_complexity,
            asset_criticality=self.asset_criticality / base,
            data_sensitivity=self.data_sensitivity / base,
            exposure_factor=self.exposure_factor / base,
        )


DEFAULT_WEIGHTS = ScoringWeights()

# Sensitivity scores per data classification level.
_DATA_SENSITIVITY: dict[str, float] = {
    DataClassification.PCI.value: 1.0,
    DataClassification.PII.value: 0.8,
    DataClassification.NONE.value: 0.1,
}

# Asset criticality from type and tags. Crown jewels and entry points
# are elevated automatically by the caller; this table covers the rest.
_ASSET_CRITICALITY: dict[str, float] = {
    "cloud_resource": 0.8,
    "domain": 0.6,
    "subdomain": 0.5,
    "ip": 0.3,
}


def _sensitivity(node: Node) -> float:
    """Return a 0-1 data sensitivity score from a DataStore node."""
    if node.node_type != "data_store":
        return 0.0
    cls = getattr(node, "data_classification", None) or DataClassification.NONE.value
    return _DATA_SENSITIVITY.get(cls, 0.1)


def _exposure(node: Node) -> float:
    """Return a 0-1 exposure score for a node.

    Entry points are by definition externally reachable. Crown jewels
    found through a chain are implicitly exposed even if not tagged
    directly — that elevation is handled by the caller.
    """
    if node.is_entry_point:
        return 1.0
    if node.is_crown_jewel:
        return 0.9
    return 0.0


def _asset_criticality(node: Node) -> float:
    """Return a 0-1 asset criticality score."""
    if node.node_type != "asset":
        return 0.0
    atype = getattr(node, "asset_type", "ip")
    return _ASSET_CRITICALITY.get(str(atype), 0.3)


@dataclass(frozen=True)
class RiskContext:
    """Extended risk factors derived from the attack target node(s) a
    finding can reach."""

    asset_criticality: float = 0.0
    data_sensitivity: float = 0.0
    exposure_factor: float = 0.0

    @property
    def has_measured_context(self) -> bool:
        """True when any factor came from real graph data rather than
        the neutral default (0.0)."""
        return self.asset_criticality > 0.0 or self.data_sensitivity > 0.0 or self.exposure_factor > 0.0


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
    asset_criticality: float
    data_sensitivity: float
    exposure_factor: float
    # Per-term contributions after weighting — these sum to ease_score.
    contributions: dict[str, float]
    risk_context: RiskContext = RiskContext()

    @property
    def complexity_is_measured(self) -> bool:
        """True when complexity came from a real CVSS vector rather than
        the configured fallback. The UI shows measured and assumed values
        differently — presenting both with equal confidence would be
        misleading."""
        return self.complexity_basis is ComplexityBasis.VECTOR


def _derive_risk_context(finding: Finding, db: "Session | None") -> RiskContext:
    """Walk YIELDS edges from the finding to find the highest-risk
    target node. Returns neutral defaults when no target is reachable or
    db is unavailable."""
    if db is None:
        return RiskContext()

    targets = (
        db.query(Edge)
        .filter(
            Edge.source_node_id == finding.id,
            Edge.edge_type == EXPLOIT_EDGE_TYPE.value,
        )
        .all()
    )
    if not targets:
        return RiskContext()

    target_ids = [t.target_node_id for t in targets]
    target_nodes = db.query(Node).filter(Node.id.in_(target_ids)).all()
    if not target_nodes:
        return RiskContext()

    crit = max((_asset_criticality(n) for n in target_nodes), default=0.0)
    sens = max((_sensitivity(n) for n in target_nodes), default=0.0)
    expo = max((_exposure(n) for n in target_nodes), default=0.0)

    return RiskContext(asset_criticality=crit, data_sensitivity=sens, exposure_factor=expo)


def score_finding(
    finding: Finding,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    db: "Session | None" = None,
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

    # Extended risk context from graph targets.
    ctx = _derive_risk_context(finding, db)

    contributions = {
        "cvss": normalized_cvss * weights.cvss,
        "exploit_public": exploit_public_term * weights.exploit_public,
        "unauthenticated": unauth_term * weights.auth_required,
        "complexity": complexity_term * weights.complexity,
        "asset_criticality": ctx.asset_criticality * weights.asset_criticality,
        "data_sensitivity": ctx.data_sensitivity * weights.data_sensitivity,
        "exposure_factor": ctx.exposure_factor * weights.exposure_factor,
    }
    total = max(0.0, min(1.0, sum(contributions.values())))

    return ScoreBreakdown(
        ease_score=total,
        normalized_cvss=normalized_cvss,
        exploit_public=exploit_public_term,
        unauthenticated=unauth_term,
        complexity=complexity,
        complexity_basis=basis,
        asset_criticality=ctx.asset_criticality,
        data_sensitivity=ctx.data_sensitivity,
        exposure_factor=ctx.exposure_factor,
        contributions=contributions,
        risk_context=ctx,
    )


def ease_score(finding: Finding, weights: ScoringWeights = DEFAULT_WEIGHTS, db: "Session | None" = None) -> float:
    """Just the number. Kept as the simple entry point for path-finding —
    score_finding() is for anything that needs to explain itself."""
    return score_finding(finding, weights, db).ease_score


# Cost that makes an edge effectively impassable to Dijkstra without
# needing a separate graph-pruning pass. Large enough that no combination
# of real edges competes with it, finite so the algorithm stays numerically
# well-behaved.
IMPASSABLE = 1e6


def edge_cost(edge: Edge, source_node: Node, weights: ScoringWeights = DEFAULT_WEIGHTS, db: "Session | None" = None) -> float:
    """Dijkstra edge weight — lower cost = easier/more realistic step.

    Manual overrides (edge.weight already set, e.g. from the "+ edge" UI
    form or a prior recompute) always take precedence over the computed
    default, on any edge type.
    """
    # A finding the tester has ruled a false positive cannot be an
    # exploitation step. Leaving it in produces a *fabricated* attack path
    # — the single worst output this tool could give, because it looks
    # exactly like a real one. Checked before the manual-weight override
    # for that reason: an FP stays impassable even if someone previously
    # hand-weighted the edge.
    if isinstance(source_node, Finding) and _is_false_positive(source_node):
        return IMPASSABLE

    if edge.weight is not None:
        return 1.0 - edge.weight

    if EdgeType(edge.edge_type) == EXPLOIT_EDGE_TYPE and isinstance(source_node, Finding):
        return 1.0 - ease_score(source_node, weights, db)

    return 0.0  # structural edge, no computed cost — see module docstring


def _is_false_positive(finding: Finding) -> bool:
    return getattr(finding, "verification_status", None) == "false-positive"
