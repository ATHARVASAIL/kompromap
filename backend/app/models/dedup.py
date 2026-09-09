"""Deduplication engine models (Phase 2).

Tracks merge candidates across findings within an engagement.
An analyst approves each merge — nothing is ever auto-merged.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class DedupScan(Base):
    """One dedup-scan run against an engagement."""

    __tablename__ = "dedup_scans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    total_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_confidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    merged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dismissed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settings_snapshot: Mapped[dict] = mapped_column(Text, nullable=False, default=dict)  # JSON-encoded


class MergeCandidate(Base):
    """A pair of findings flagged as potentially duplicate."""

    __tablename__ = "merge_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("dedup_scans.id", ondelete="CASCADE"), nullable=False)
    engagement_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    # The pair being compared
    finding_a_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    finding_b_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    # Per-dimension scores (0-1 each)
    url_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    endpoint_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    param_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cwe_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    request_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    response_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Composite: weighted average of dimensions above
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Threshold used when this candidate was produced
    threshold_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)

    # Status lifecycle: pending -> merged | dismissed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|merged|dismissed

    # Analyst notes on the decision
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    scan: Mapped["DedupScan"] = relationship("DedupScan")
