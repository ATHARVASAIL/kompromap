"""Deduplication API endpoints.

These endpoints are protected by the same API-key middleware as the rest
of the surface — see app/main.py's `_protected` list.

The analyst workflow is:
  1. POST /api/dedup/scan — run the engine, get candidates
  2. GET  /api/dedup/scans — list past scans for this engagement
  3. GET  /api/dedup/scans/{scan_id}/candidates — review candidates
  4. POST /api/dedup/candidates/{candidate_id}/resolve — apply a decision
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Finding, Node
from app.models.enums import NodeType
from app.schemas.dedup import (
    DedupScanCreate,
    DedupScanRead,
    MergeCandidateAction,
    MergeCandidateSummary,
)
from app.services.dedup import (
    get_candidates_for_scan,
    get_scan,
    get_scans_for_engagement,
    resolve_candidate,
    run_scan,
)
from app.services.engagements import resolve_engagement_id

router = APIRouter(prefix="/dedup", tags=["dedup"])


@router.post("/scan", response_model=DedupScanRead, status_code=201)
def create_scan(
    payload: DedupScanCreate,
    engagement_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    """Run the deduplication engine against an engagement.

    Produces a DedupScan record populated with MergeCandidates for every
    finding pair above the similarity threshold. The analyst reviews
    candidates and resolves each one — the tool never acts unilaterally.
    """
    resolved = resolve_engagement_id(db, engagement_id)
    try:
        scan = run_scan(
            db,
            engagement_id=resolved,
            threshold=payload.similarity_threshold,
            signals=payload.signals,
            weights=payload.weights,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    return DedupScanRead.model_validate(scan)


@router.get("/scans", response_model=list[DedupScanRead])
def list_scans(
    engagement_id: uuid.UUID | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List recent dedup scans for an engagement, newest first."""
    resolved = resolve_engagement_id(db, engagement_id)
    scans = get_scans_for_engagement(db, resolved, limit=limit)
    return [DedupScanRead.model_validate(s) for s in scans]


@router.get("/scans/{scan_id}", response_model=DedupScanRead)
def get_scan_detail(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single scan by ID."""
    scan = get_scan(db, scan_id)
    if scan is None:
        raise HTTPException(404, "Scan not found")
    return DedupScanRead.model_validate(scan)


def _candidate_summary(db: Session, candidate) -> MergeCandidateSummary:
    """Build a summary with finding titles resolved from the DB."""
    a_title = _finding_title(db, candidate.finding_a_id)
    b_title = _finding_title(db, candidate.finding_b_id)
    return MergeCandidateSummary(
        id=candidate.id,
        finding_a_id=candidate.finding_a_id,
        finding_b_id=candidate.finding_b_id,
        finding_a_title=a_title,
        finding_b_title=b_title,
        signal_scores=candidate.signal_scores,
        overall_score=candidate.overall_score,
        high_impact=candidate.high_impact,
        action=candidate.action,
        created_at=candidate.created_at,
    )


def _finding_title(db: Session, finding_id: uuid.UUID) -> str:
    node = db.get(Node, finding_id)
    if node is None or node.node_type != NodeType.FINDING.value:
        return f"[unknown: {finding_id}]"
    finding = db.get(Finding, finding_id)
    if finding is None:
        return f"[deleted: {finding_id}]"
    return finding.title


@router.get("/scans/{scan_id}/candidates", response_model=list[MergeCandidateSummary])
def list_candidates(
    scan_id: uuid.UUID,
    action: str | None = None,
    db: Session = Depends(get_db),
):
    """List candidates for a scan, optionally filtered by action status."""
    scan = get_scan(db, scan_id)
    if scan is None:
        raise HTTPException(404, "Scan not found")

    candidates = get_candidates_for_scan(db, scan_id, action=action)
    return [_candidate_summary(db, c) for c in candidates]


@router.post("/candidates/{candidate_id}/resolve")
def resolve_candidate_endpoint(
    candidate_id: uuid.UUID,
    payload: MergeCandidateAction,
    db: Session = Depends(get_db),
):
    """Apply the analyst's decision to a merge candidate.

    Actions:
      - ``merge`` — keep one finding (pass its ID as kept_id), close the other
      - ``keep_separate`` — same bug, different context; dismiss the suggestion
      - ``mark_duplicate`` — both are duplicates; close both without merging
    """
    try:
        result = resolve_candidate(
            db,
            candidate_id=candidate_id,
            action=payload.action,
            kept_id=payload.kept_id,
            analyst_note=payload.analyst_note,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    return {
        "id": result.id,
        "action": result.action,
        "kept_id": result.kept_id,
        "analyst_note": result.analyst_note,
        "resolved_at": result.resolved_at.isoformat() if result.resolved_at else None,
    }
