"""Edge model — the adjacency-list table connecting nodes.

Per spec §6: "edges(id, source_node_id, target_node_id, edge_type, weight,
metadata)". `weight` is populated once path-finding lands in Phase 4 (the
ease_score formula in spec §4 needs a configurable-weights story that's out
of scope here); it's nullable until then.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import EdgeType

# JSONB on Postgres (native, indexable); plain JSON on other dialects.
JsonDict = JSON().with_variant(JSONB, "postgresql")


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edge_type: Mapped[EdgeType] = mapped_column(String(32), nullable=False)

    # Path-finding cost input. cost = 1 - weight (ease_score); see spec §4.
    # Populated in Phase 4 (path-finding engine) — nullable until then.
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Renamed from spec's "metadata" — that name collides with SQLAlchemy's
    # own Base.metadata attribute, so this is exposed to the API as
    # "metadata" but stored as edge_metadata on the model/column.
    edge_metadata: Mapped[dict | None] = mapped_column(JsonDict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source = relationship(
        "Node", foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target = relationship(
        "Node", foreign_keys=[target_node_id], back_populates="incoming_edges"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"<Edge {self.edge_type} {self.source_node_id} -> {self.target_node_id}>"
