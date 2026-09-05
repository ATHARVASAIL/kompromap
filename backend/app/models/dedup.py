"""Deduplication engine models.

A dedup scan compares every pair of findings within an engagement and
produces MergeCandidates — pairs of findings that look like the same
vulnerability reported through multiple tools or manual entries.

The analyst is the only one who can act on a candidate. The API exposes
three actions:
  - **merge** — keep one finding, close the other as a duplicate
  - **keep separate** — dismiss the suggestion (same bug, different context)
  - **mark duplicate** — close both without merging (e.g. both are FP)

Never auto-merges. Never touches verification_status or cvss_score without
the analyst's explicit merge action.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class DedupScan(Base):
    """A single run of the deduplication engine against one engagement.

    Scans are immutable once created — re-running creates a new scan so
    the history of "what did the tool suggest when?" is preserved.
    """

    __tablename__ = "dedup_scans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Scan configuration — preserved so results are reproducible.
    similarity_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    # The set of signal types actually used in this scan.
    signals: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # Aggregate outcome.
    candidates_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Pre-filtered out before surfacing to the analyst.
    candidates_filtered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    candidates = relationship(
        "MergeCandidate",
        back_populates="scan",
        cascade="all, delete-orphan",
    )


class MergeCandidate(Base):
    """One pair of findings that look like duplicates.

    The similarity score is 0.0–1.0. A threshold controls what surfaces
    to the analyst — low-confidence suggestions are silently dropped
    rather than cluttering the UI with noise.

    The ``action`` field tracks what the analyst decided:
      - ``pending`` — awaiting analyst decision
      - ``merge`` — findings were merged; ``kept_id`` is the survivor
      - ``keep_separate`` — same bug, different enough context to keep both
      - ``mark_duplicate`` — both closed as duplicates of each other

    ``high_impact`` is set during scoring. High-impact pairs (CVSS >= 7.0
    on either side) are **never auto-merged** — the analyst must explicitly
    approve any merge that touches a high-severity finding.
    """

    __tablename__ = "merge_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dedup_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The two findings being compared.
    finding_a_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    finding_b_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    # Signal-level breakdown — which dimensions matched and by how much.
    # Keys: "title", "cwe", "owasp", "url", "endpoint", "params"
    # Values: 0.0–1.0 per signal.
    signal_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)

    # If either finding has CVSS >= high_impact_threshold, this is True.
    high_impact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Analyst action.
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # Which finding was kept (set when action == "merge").
    kept_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # Analyst's reasoning — optional free text.
    analyst_note: Mapped[str | None] = mapped_column(String, nullable=True)

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scan = relationship("DedupScan", back_populates="candidates")

    # Valid actions the analyst can set.
    _VALID_ACTIONS = frozenset({"pending", "merge", "keep_separate", "mark_duplicate"})

    @classmethod
    def validate_action(cls, action: str) -> str:
        if action not in cls._VALID_ACTIONS:
            raise ValueError(
                f"Invalid action {action!r}; must be one of {sorted(cls._VALID_ACTIONS)}"
            )
        return action
