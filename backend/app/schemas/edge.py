import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import EdgeType


class EdgeCreate(BaseModel):
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: EdgeType
    weight: float | None = None
    metadata: dict | None = None


class EdgeUpdate(BaseModel):
    edge_type: EdgeType | None = None
    weight: float | None = None
    metadata: dict | None = None


class EdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: EdgeType
    weight: float | None
    metadata: dict | None = None
    created_at: datetime

    @classmethod
    def from_orm_edge(cls, edge) -> "EdgeRead":
        return cls(
            id=edge.id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            edge_type=edge.edge_type,
            weight=edge.weight,
            metadata=edge.edge_metadata,
            created_at=edge.created_at,
        )
