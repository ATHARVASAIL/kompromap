"""Weighted shortest-path engine (spec §5 Phase 2 differentiator / §7 Phase
4): given entry points and crown jewels, find the lowest-cost (= most
realistic, not just fewest-hop) chain between them, using the ease_score
scoring from app/services/scoring.py as edge weights.

Dijkstra's shortest path minimizes total edge cost, and cost = 1 -
ease_score (see scoring.py), so the "shortest path" here is exactly the
spec's "most likely/most damaging path" — an easy multi-hop chain can beat
a single hard hop.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import networkx as nx

from app.models import Edge, Node
from app.services.scoring import ScoringWeights, edge_cost


@dataclass
class PathResult:
    entry_point: Node
    crown_jewel: Node
    total_cost: float
    nodes: list[Node]
    edges: list[Edge]


@dataclass
class PathfindingReport:
    paths: list[PathResult] = field(default_factory=list)
    unreachable_entry_points: list[Node] = field(default_factory=list)


def build_weighted_graph(
    nodes: list[Node], edges: list[Edge], weights: ScoringWeights
) -> nx.DiGraph:
    nodes_by_id = {n.id: n for n in nodes}
    g = nx.DiGraph()
    for node in nodes:
        g.add_node(node.id)
    for edge in edges:
        source_node = nodes_by_id.get(edge.source_node_id)
        if source_node is None or edge.target_node_id not in nodes_by_id:
            continue  # edge points outside the filtered node set, skip
        cost = edge_cost(edge, source_node, weights)
        g.add_edge(edge.source_node_id, edge.target_node_id, cost=cost, edge=edge)
    return g


def _reconstruct(
    graph: nx.DiGraph,
    nodes_by_id: dict[uuid.UUID, Node],
    node_id_path: list[uuid.UUID],
) -> tuple[list[Node], list[Edge]]:
    node_path = [nodes_by_id[nid] for nid in node_id_path]
    edge_path = [
        graph.edges[node_id_path[i], node_id_path[i + 1]]["edge"]
        for i in range(len(node_id_path) - 1)
    ]
    return node_path, edge_path


def best_paths_from_entry_point(
    graph: nx.DiGraph,
    nodes_by_id: dict[uuid.UUID, Node],
    entry_point: Node,
    crown_jewels: list[Node],
) -> list[PathResult]:
    """The single best (lowest-cost) path from this entry point to *each*
    reachable crown jewel — spec §5's "show all paths from this entry
    point." Sorted cheapest-first."""
    if entry_point.id not in graph:
        return []

    try:
        costs, paths = nx.single_source_dijkstra(graph, entry_point.id, weight="cost")
    except nx.NodeNotFound:
        return []

    results = []
    for cj in crown_jewels:
        if cj.id == entry_point.id or cj.id not in costs:
            continue
        node_path, edge_path = _reconstruct(graph, nodes_by_id, paths[cj.id])
        results.append(
            PathResult(
                entry_point=entry_point,
                crown_jewel=cj,
                total_cost=costs[cj.id],
                nodes=node_path,
                edges=edge_path,
            )
        )
    results.sort(key=lambda r: r.total_cost)
    return results


def best_path_to_any_crown_jewel(
    graph: nx.DiGraph,
    nodes_by_id: dict[uuid.UUID, Node],
    entry_point: Node,
    crown_jewels: list[Node],
) -> PathResult | None:
    """The single easiest path from this entry point to *any* crown jewel."""
    candidates = best_paths_from_entry_point(graph, nodes_by_id, entry_point, crown_jewels)
    return candidates[0] if candidates else None


def find_best_paths_report(
    nodes: list[Node],
    edges: list[Edge],
    entry_points: list[Node],
    crown_jewels: list[Node],
    weights: ScoringWeights,
) -> PathfindingReport:
    """For every entry point, the single easiest path to any crown jewel —
    spec §5's "show the easiest path to any crown jewel," run across the
    whole engagement rather than one specific entry point."""
    graph = build_weighted_graph(nodes, edges, weights)
    nodes_by_id = {n.id: n for n in nodes}

    report = PathfindingReport()
    for ep in entry_points:
        best = best_path_to_any_crown_jewel(graph, nodes_by_id, ep, crown_jewels)
        if best is not None:
            report.paths.append(best)
        else:
            report.unreachable_entry_points.append(ep)

    report.paths.sort(key=lambda r: r.total_cost)
    return report
