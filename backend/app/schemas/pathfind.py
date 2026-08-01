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


class PathNode(BaseModel):
    id: uuid.UUID
    node_type: NodeType
    label: str


class PathEdge(BaseModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID
    edge_type: EdgeType
    cost: float


class PathResultResponse(BaseModel):
    entry_point: PathNode
    crown_jewel: PathNode
    total_cost: float
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
