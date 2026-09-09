"""Pydantic schemas for the dedup API."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DimensionScores(BaseModel):
    url_similarity: float
    endpoint_similarity: float
    param_similarity: float
    cwe_similarity: float
    request_similarity: float
    response_similarity: float


class MergeCandidateRead(BaseModel):
    id: UUID
    scan_id: UUID
    engagement_id: UUID
    finding_a_id: UUID
    finding_b_id: UUID
    dimensions: DimensionScores
    overall_score: float
    threshold_used: float
    status: str
    notes: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class MergeCandidateResolve(BaseModel):
    action: str = Field(pattern="^(merged|dismissed)$")
    notes: str | None = None


class DedupScanRead(BaseModel):
    id: UUID
    engagement_id: UUID
    created_at: datetime
    total_candidates: int
    high_confidence_count: int
    merged_count: int
    dismissed_count: int
    settings_snapshot: dict[str, Any]

    model_config = {"from_attributes": True}


class DedupScanRequest(BaseModel):
    threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class DedupScanResponse(BaseModel):
    scan: DedupScanRead
    candidates: list[MergeCandidateRead]
