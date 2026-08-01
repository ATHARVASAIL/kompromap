"""Response shape for GET /api/graph.

Deliberately close to Cytoscape.js's elements format
({data: {...}}) so the Phase 3 frontend can feed this response straight
into cy.add(...) with minimal reshaping.
"""
import uuid

from pydantic import BaseModel

from app.models.enums import EdgeType, NodeType


class GraphNode(BaseModel):
    id: uuid.UUID
    node_type: NodeType
    label: str
    is_entry_point: bool
    is_crown_jewel: bool
    properties: dict


class GraphEdge(BaseModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID
    edge_type: EdgeType
    weight: float | None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
