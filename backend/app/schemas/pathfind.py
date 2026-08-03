import uuid

from pydantic import BaseModel, Field

from app.models.enums import EdgeType, NodeType


class ScoringWeightsInput(BaseModel):
    """Configurable scoring weights (spec §5 Phase 2: "Configurable scoring
    weights (per engagement, since risk appetite differs bank vs.
    ecommerce client)"). Needn't sum to 1.0 — Dijkstra only cares about
    relative ordering between edges."""

    cvss: float = 0.4
    exploit_public: float = 0.3
    auth_required: float = 0.2
    complexity: float = 0.1
    default_complexity: float = Field(
        default=0.5,
        description=(
            "Complexity isn't a stored Finding property (see app/services/scoring.py), "
            "so this uniform default stands in for it. 0 = treat every finding as trivial, "
            "1 = treat every finding as maximally complex."
        ),
    )


class PathfindRequest(BaseModel):
    entry_point_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Defaults to every node tagged is_entry_point if omitted.",
    )
    crown_jewel_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Defaults to every node tagged is_crown_jewel if omitted.",
    )
    engagement_id: uuid.UUID | None = Field(
        default=None, description="Defaults to the active engagement if omitted."
    )
    weights: ScoringWeightsInput = Field(default_factory=ScoringWeightsInput)


class ScoreBreakdownResponse(BaseModel):
    """Why a finding scored the way it did.

    Path-finding previously returned an opaque total cost, which made the
    most obvious question — "why is this chain ranked above that one?" —
    unanswerable from the UI. Each weighted term is now returned
    separately, along with whether complexity was measured from a real
    CVSS vector or assumed from the configured default.
    """

    ease_score: float
    normalized_cvss: float
    exploit_public: float
    unauthenticated: float
    complexity: float
    complexity_measured: bool = Field(
        description="True when complexity came from a CVSS vector rather than the fallback. "
        "The UI distinguishes these — presenting an assumed value with the same "
        "confidence as a measured one would be misleading."
    )
    contributions: dict[str, float] = Field(
        description="Per-term contribution after weighting. Sums to ease_score."
    )


class PathNode(BaseModel):
    id: uuid.UUID
    node_type: NodeType
    label: str
    # Populated for Finding nodes so the UI can show severity inline on a
    # path without a second round-trip per node.
    cvss_score: float | None = None
    cvss_vector: str | None = None
    is_entry_point: bool = False
    is_crown_jewel: bool = False


class PathEdge(BaseModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID
    edge_type: EdgeType
    cost: float
    # Only exploitation steps (YIELDS from a Finding) carry a computed
    # score; structural edges are free and leave this null.
    breakdown: ScoreBreakdownResponse | None = None


class PathResultResponse(BaseModel):
    entry_point: PathNode
    crown_jewel: PathNode
    total_cost: float
    exploit_step_count: int = Field(
        default=0,
        description="How many edges in this chain are actual exploitation steps "
        "rather than structural links. A 7-hop chain with 2 exploits is easier "
        "than a 3-hop chain with 3.",
    )
    hardest_step_cost: float = Field(
        default=0.0,
        description="Cost of the single most expensive edge — the chain's bottleneck, "
        "and usually the most useful thing to remediate.",
    )
    nodes: list[PathNode]
    edges: list[PathEdge]


class PathfindBestResponse(BaseModel):
    """Response for POST /api/pathfind/best — one best path per entry
    point, plus which entry points couldn't reach any crown jewel."""

    paths: list[PathResultResponse]
    unreachable_entry_points: list[PathNode]


class PathfindFromResponse(BaseModel):
    """Response for POST /api/pathfind/from/{entry_point_id} — one best
    path to each reachable crown jewel from this specific entry point, plus
    which crown jewels weren't reachable at all."""

    paths: list[PathResultResponse]
    unreachable_crown_jewels: list[PathNode]
