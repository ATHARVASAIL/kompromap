"""GET /api/graph — the whole engagement graph, loaded into NetworkX (per
spec §6: relational storage, in-memory NetworkX for algorithms on request)
and serialized into a Cytoscape.js-friendly shape.

Loading into NetworkX here even though Phase 2 doesn't run any graph
algorithms yet is deliberate: it's the seam Phase 4's path-finding will
plug into (`build_networkx_graph` below), and it's a natural place to
validate the graph is well-formed (no edges pointing at nodes that don't
exist, etc.) before handing it to the frontend.
"""
import uuid

import networkx as nx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Edge, Node, NodeType
from app.models.enums import EdgeType
from app.schemas.graph import GraphEdge, GraphNode, GraphResponse
from app.services.engagements import resolve_engagement_id

router = APIRouter(prefix="/graph", tags=["graph"])

# Properties to surface per node type in the generic `properties` bag the
# frontend's detail panel will render (Phase 3). Kept centralized here
# rather than duplicated per node type.
_TYPE_PROPERTIES: dict[NodeType, tuple[str, ...]] = {
    NodeType.ASSET: ("name", "asset_type", "in_scope", "tags"),
    NodeType.SERVICE: ("port", "protocol", "banner", "tech_stack"),
    NodeType.WEB_APPLICATION: ("name", "base_url", "tech_stack", "auth_type"),
    NodeType.ENDPOINT: ("path", "method", "params", "requires_auth", "documented"),
    NodeType.CREDENTIAL: ("cred_type", "scope", "obtained_via_finding_id"),
    NodeType.ACCOUNT: ("username", "privilege_level"),
    NodeType.DATA_STORE: ("name", "data_classification", "record_count_estimate"),
    NodeType.FINDING: (
        "title",
        "cwe",
        "owasp_category",
        "cvss_score",
        "exploit_public",
        "auth_required",
        "status",
    ),
}

_LABEL_FIELD: dict[NodeType, str] = {
    NodeType.ASSET: "name",
    NodeType.SERVICE: "port",
    NodeType.WEB_APPLICATION: "name",
    NodeType.ENDPOINT: "path",
    NodeType.CREDENTIAL: "cred_type",
    NodeType.ACCOUNT: "username",
    NodeType.DATA_STORE: "name",
    NodeType.FINDING: "title",
}


def build_networkx_graph(nodes: list[Node], edges: list[Edge]) -> nx.DiGraph:
    """Load a set of nodes/edges into a directed NetworkX graph. Path-
    finding (Phase 4) builds on this rather than re-querying the DB."""
    g = nx.DiGraph()
    for node in nodes:
        g.add_node(node.id, node_type=node.node_type, node=node)
    for edge in edges:
        g.add_edge(edge.source_node_id, edge.target_node_id, edge_type=edge.edge_type, edge=edge)
    return g


def _node_label(node: Node) -> str:
    field = _LABEL_FIELD[NodeType(node.node_type)]
    return str(getattr(node, field))


def _node_properties(node: Node) -> dict:
    fields = _TYPE_PROPERTIES[NodeType(node.node_type)]
    return {f: getattr(node, f) for f in fields}


@router.get("", response_model=GraphResponse)
def get_graph(
    node_type: NodeType | None = Query(default=None),
    in_scope_only: bool = Query(default=False, description="Drop out-of-scope assets"),
    min_cvss: float | None = Query(default=None, description="Drop findings below this score"),
    engagement_id: uuid.UUID | None = Query(default=None, description="Defaults to the active engagement"),
    db: Session = Depends(get_db),
):
    resolved_engagement_id = resolve_engagement_id(db, engagement_id)
    node_stmt = select(Node).where(Node.engagement_id == resolved_engagement_id)
    if node_type is not None:
        node_stmt = node_stmt.where(Node.node_type == node_type.value)
    nodes = list(db.scalars(node_stmt))

    if in_scope_only:
        nodes = [
            n for n in nodes if NodeType(n.node_type) != NodeType.ASSET or getattr(n, "in_scope", True)
        ]
    if min_cvss is not None:
        nodes = [
            n
            for n in nodes
            if NodeType(n.node_type) != NodeType.FINDING or (getattr(n, "cvss_score", 0) or 0) >= min_cvss
        ]

    node_ids = {n.id for n in nodes}
    edges = [
        e
        for e in db.scalars(select(Edge))
        if e.source_node_id in node_ids and e.target_node_id in node_ids
    ]

    # Building the NetworkX graph here validates structure even though
    # nothing queries it yet in Phase 2 — see module docstring.
    build_networkx_graph(nodes, edges)

    return GraphResponse(
        nodes=[
            GraphNode(
                id=n.id,
                node_type=NodeType(n.node_type),
                label=_node_label(n),
                is_entry_point=n.is_entry_point,
                is_crown_jewel=n.is_crown_jewel,
                properties=_node_properties(n),
            )
            for n in nodes
        ],
        edges=[
            GraphEdge(
                id=e.id,
                source=e.source_node_id,
                target=e.target_node_id,
                edge_type=EdgeType(e.edge_type),
                weight=e.weight,
            )
            for e in edges
        ],
    )
