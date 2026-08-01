import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.graph import GraphResponse


class SnapshotCreate(BaseModel):
    label: str


class SnapshotSummary(BaseModel):
    """List view — metadata only, not the full graph payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    engagement_id: uuid.UUID
    label: str
    node_count: int
    edge_count: int
    created_at: datetime


class SnapshotDetail(SnapshotSummary):
    data: GraphResponse


class DiffEntry(BaseModel):
    id: uuid.UUID
    label: str
    node_type: str | None = None  # present for node entries, absent for edges
    edge_type: str | None = None  # present for edge entries, absent for nodes


class GraphDiff(BaseModel):
    """What changed between a snapshot and the comparison point (another
    snapshot, or the current live graph if none given)."""

    nodes_added: list[DiffEntry]
    nodes_removed: list[DiffEntry]
    edges_added: list[DiffEntry]
    edges_removed: list[DiffEntry]
