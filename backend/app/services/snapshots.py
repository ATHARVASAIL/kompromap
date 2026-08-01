"""Snapshot capture and diffing (spec §5 Phase 4 / §7 Phase 6: "Snapshot
history — compare the graph at engagement start vs. after further
testing").
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.graph import _node_label, _node_properties
from app.models import Edge, Node, Snapshot


def _capture_graph_dict(db: Session, engagement_id: uuid.UUID) -> dict:
    nodes = list(db.scalars(select(Node).where(Node.engagement_id == engagement_id)))
    node_ids = {n.id for n in nodes}
    edges = [
        e for e in db.scalars(select(Edge)) if e.source_node_id in node_ids and e.target_node_id in node_ids
    ]

    return {
        "nodes": [
            {
                "id": str(n.id),
                "node_type": n.node_type,
                "label": _node_label(n),
                "is_entry_point": n.is_entry_point,
                "is_crown_jewel": n.is_crown_jewel,
                "properties": _node_properties(n),
            }
            for n in nodes
        ],
        "edges": [
            {
                "id": str(e.id),
                "source": str(e.source_node_id),
                "target": str(e.target_node_id),
                "edge_type": e.edge_type,
                "weight": e.weight,
            }
            for e in edges
        ],
    }


def create_snapshot(db: Session, engagement_id: uuid.UUID, label: str) -> Snapshot:
    data = _capture_graph_dict(db, engagement_id)
    snapshot = Snapshot(
        engagement_id=engagement_id,
        label=label,
        node_count=len(data["nodes"]),
        edge_count=len(data["edges"]),
        data=data,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def diff_graph_dicts(base: dict, compare: dict) -> dict:
    """added = present in `compare` but not `base`; removed = the reverse."""
    base_node_ids = {n["id"] for n in base["nodes"]}
    compare_node_ids = {n["id"] for n in compare["nodes"]}
    base_edge_ids = {e["id"] for e in base["edges"]}
    compare_edge_ids = {e["id"] for e in compare["edges"]}

    base_nodes_by_id = {n["id"]: n for n in base["nodes"]}
    compare_nodes_by_id = {n["id"]: n for n in compare["nodes"]}
    base_edges_by_id = {e["id"]: e for e in base["edges"]}
    compare_edges_by_id = {e["id"]: e for e in compare["edges"]}

    return {
        "nodes_added": [
            {
                "id": nid,
                "label": compare_nodes_by_id[nid]["label"],
                "node_type": compare_nodes_by_id[nid]["node_type"],
            }
            for nid in compare_node_ids - base_node_ids
        ],
        "nodes_removed": [
            {"id": nid, "label": base_nodes_by_id[nid]["label"], "node_type": base_nodes_by_id[nid]["node_type"]}
            for nid in base_node_ids - compare_node_ids
        ],
        "edges_added": [
            {
                "id": eid,
                "label": compare_edges_by_id[eid]["edge_type"],
                "edge_type": compare_edges_by_id[eid]["edge_type"],
            }
            for eid in compare_edge_ids - base_edge_ids
        ],
        "edges_removed": [
            {"id": eid, "label": base_edges_by_id[eid]["edge_type"], "edge_type": base_edges_by_id[eid]["edge_type"]}
            for eid in base_edge_ids - compare_edge_ids
        ],
    }


def diff_snapshot(db: Session, base_snapshot: Snapshot, compare_snapshot: Snapshot | None) -> dict:
    """Diff `base_snapshot` against `compare_snapshot`, or against the
    current live graph state if compare_snapshot is None (the common case:
    "how has this engagement changed since I took this snapshot")."""
    compare_data = (
        compare_snapshot.data
        if compare_snapshot is not None
        else _capture_graph_dict(db, base_snapshot.engagement_id)
    )
    return diff_graph_dicts(base_snapshot.data, compare_data)
