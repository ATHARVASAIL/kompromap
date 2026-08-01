"""Path-finding endpoints (spec §5 Phase 2 / §7 Phase 4):

- POST /api/pathfind/best   — "show the easiest path to any crown jewel,"
  across every entry point in the engagement (or a specified subset).
- POST /api/pathfind/from/{entry_point_id} — "show all paths from this
  entry point," one best path per reachable crown jewel.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.graph import _node_label
from app.core.db import get_db
from app.models import Edge, Node, NodeType
from app.schemas.pathfind import (
    PathEdge,
    PathfindBestResponse,
    PathfindFromResponse,
    PathfindRequest,
    PathNode,
    PathResultResponse,
    ScoringWeightsInput,
)
from app.services.pathfinding import (
    best_paths_from_entry_point,
    build_weighted_graph,
    find_best_paths_report,
)
from app.services.engagements import resolve_engagement_id
from app.services.scoring import ScoringWeights

router = APIRouter(prefix="/pathfind", tags=["pathfind"])


def _to_scoring_weights(w: ScoringWeightsInput) -> ScoringWeights:
    return ScoringWeights(
        cvss=w.cvss,
        exploit_public=w.exploit_public,
        auth_required=w.auth_required,
        complexity=w.complexity,
        default_complexity=w.default_complexity,
    )


def _to_path_node(node: Node) -> PathNode:
    return PathNode(id=node.id, node_type=NodeType(node.node_type), label=_node_label(node))


def _to_path_result(p) -> PathResultResponse:
    return PathResultResponse(
        entry_point=_to_path_node(p.entry_point),
        crown_jewel=_to_path_node(p.crown_jewel),
        total_cost=p.total_cost,
        nodes=[_to_path_node(n) for n in p.nodes],
        edges=[
            PathEdge(
                id=e.id,
                source=e.source_node_id,
                target=e.target_node_id,
                edge_type=e.edge_type,
                cost=1.0 - e.weight if e.weight is not None else 0.0,
            )
            for e in p.edges
        ],
    )


def _resolve_nodes(
    all_nodes: list[Node], ids: list[uuid.UUID] | None, flag_attr: str, label: str
) -> list[Node]:
    nodes_by_id = {n.id: n for n in all_nodes}
    if ids is not None:
        resolved = [nodes_by_id[i] for i in ids if i in nodes_by_id]
        missing = set(ids) - {n.id for n in resolved}
        if missing:
            raise HTTPException(422, f"Unknown {label}: {sorted(str(m) for m in missing)}")
        return resolved
    return [n for n in all_nodes if getattr(n, flag_attr)]


@router.post("/best", response_model=PathfindBestResponse)
def pathfind_best(payload: PathfindRequest, db: Session = Depends(get_db)):
    resolved_engagement_id = resolve_engagement_id(db, payload.engagement_id)
    all_nodes = list(db.scalars(select(Node).where(Node.engagement_id == resolved_engagement_id)))
    node_ids = {n.id for n in all_nodes}
    all_edges = [
        e for e in db.scalars(select(Edge)) if e.source_node_id in node_ids and e.target_node_id in node_ids
    ]

    entry_points = _resolve_nodes(all_nodes, payload.entry_point_ids, "is_entry_point", "entry_point_ids")
    crown_jewels = _resolve_nodes(all_nodes, payload.crown_jewel_ids, "is_crown_jewel", "crown_jewel_ids")

    if not entry_points:
        raise HTTPException(
            422, "No entry points found — tag at least one node is_entry_point, or pass entry_point_ids"
        )
    if not crown_jewels:
        raise HTTPException(
            422, "No crown jewels found — tag at least one node is_crown_jewel, or pass crown_jewel_ids"
        )

    report = find_best_paths_report(
        all_nodes, all_edges, entry_points, crown_jewels, _to_scoring_weights(payload.weights)
    )

    return PathfindBestResponse(
        paths=[_to_path_result(p) for p in report.paths],
        unreachable_entry_points=[_to_path_node(n) for n in report.unreachable_entry_points],
    )


@router.post("/from/{entry_point_id}", response_model=PathfindFromResponse)
def pathfind_from_entry_point(
    entry_point_id: uuid.UUID, payload: PathfindRequest, db: Session = Depends(get_db)
):
    resolved_engagement_id = resolve_engagement_id(db, payload.engagement_id)
    all_nodes = list(db.scalars(select(Node).where(Node.engagement_id == resolved_engagement_id)))
    node_ids = {n.id for n in all_nodes}
    all_edges = [
        e for e in db.scalars(select(Edge)) if e.source_node_id in node_ids and e.target_node_id in node_ids
    ]
    nodes_by_id = {n.id: n for n in all_nodes}

    entry_point = nodes_by_id.get(entry_point_id)
    if entry_point is None:
        raise HTTPException(404, "entry_point_id does not reference an existing node in this engagement")

    crown_jewels = _resolve_nodes(all_nodes, payload.crown_jewel_ids, "is_crown_jewel", "crown_jewel_ids")
    if not crown_jewels:
        raise HTTPException(
            422, "No crown jewels found — tag at least one node is_crown_jewel, or pass crown_jewel_ids"
        )

    weights = _to_scoring_weights(payload.weights)
    graph = build_weighted_graph(all_nodes, all_edges, weights)
    results = best_paths_from_entry_point(graph, nodes_by_id, entry_point, crown_jewels)

    reached_ids = {r.crown_jewel.id for r in results}
    unreachable = [cj for cj in crown_jewels if cj.id not in reached_ids]

    return PathfindFromResponse(
        paths=[_to_path_result(p) for p in results],
        unreachable_crown_jewels=[_to_path_node(cj) for cj in unreachable],
    )
