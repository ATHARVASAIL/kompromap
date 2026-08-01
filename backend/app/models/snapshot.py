"""Snapshot model (spec §5 Phase 4 / §7 Phase 6: "Snapshot history — compare
the graph at engagement start vs. after further testing").

A snapshot stores a full denormalized copy of the graph (nodes + edges) at
the moment it was taken, as JSON — not an incremental diff-based version
history. For an engagement-sized graph (spec §6: "hundreds, not millions"
of nodes) a full copy per snapshot is simple, correct, and cheap enough;
incremental versioning would add real complexity for no benefit at this
scale.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

JsonDict = JSON().with_variant(JSONB, "postgresql")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # {"nodes": [{...}], "edges": [{...}]} — same shape as GraphResponse,
    # captured at snapshot time.
    data: Mapped[dict] = mapped_column(JsonDict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"<Snapshot {self.label!r} ({self.node_count} nodes, {self.edge_count} edges)>"
