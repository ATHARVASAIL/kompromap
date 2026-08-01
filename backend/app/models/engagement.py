"""Engagement model (spec §5 Phase 4 / §7 Phase 6: "Multiple
engagements/workspaces, each with its own isolated graph").

Design note: `is_active` marks the single engagement that node/edge
creation defaults into when no `engagement_id` is given explicitly, and
that list/graph/pathfind/reporting endpoints filter to by default. This
"one active workspace" model matches the spec's own stated scope for v1
("single-user local tool", §6) — no concurrent multi-user story to worry
about — and it's what keeps every earlier phase's API calls working
unmodified: a "Default Engagement" is auto-created and activated the first
time anything touches the graph, so code that's never heard of engagements
still ends up scoped into one.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"<Engagement {self.name!r} active={self.is_active}>"
