"""Pydantic schemas for the deduplication API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- Scan schemas ---------------------------------------------------------


class DedupScanCreate(BaseModel):
    """Request body for triggering a dedup scan."""

    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum overall score for a pair to surface as a candidate (0.0–1.0)",
    )
    signals: list[str] | None = Field(
        default=None,
        description="Which signal dimensions to use. Available: title, cwe, owasp, location, endpoint, params",
    )
    weights: dict[str, float] | None = Field(
        default=None,
        description="Per-signal weights (must include all selected signals). Sums are normalized automatically.",
    )


class DedupScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    engagement_id: uuid.UUID
    similarity_threshold: float
    signals: list[str]
    candidates_found: int
    candidates_filtered: int
    created_at: datetime


# --- Candidate schemas ----------------------------------------------------


class MergeCandidateRead(BaseModel):
    """One pair of findings that look like duplicates."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_id: uuid.UUID
    finding_a_id: uuid.UUID
    finding_b_id: uuid.UUID

    # Per-signal scores — shows the analyst *why* the tool thinks these match.
    signal_scores: dict[str, float]
    overall_score: float

    # Whether either finding is high-impact (CVSS >= 7.0).
    high_impact: bool

    # Current analyst action on this candidate.
    action: str
    kept_id: uuid.UUID | None
    analyst_note: str | None
    resolved_at: datetime | None

    created_at: datetime


class MergeCandidateAction(BaseModel):
    """Request body for acting on a merge candidate."""

    action: str = Field(
        description="One of: merge, keep_separate, mark_duplicate",
    )
    kept_id: uuid.UUID | None = Field(
        default=None,
        description="Required when action is 'merge' — which finding survives.",
    )
    analyst_note: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional reasoning from the analyst.",
    )


class MergeCandidateSummary(BaseModel):
    """Lightweight candidate with finding titles filled in for list display."""

    id: uuid.UUID
    finding_a_id: uuid.UUID
    finding_b_id: uuid.UUID
    finding_a_title: str
    finding_b_title: str
    signal_scores: dict[str, float]
    overall_score: float
    high_impact: bool
    action: str
    created_at: datetime
