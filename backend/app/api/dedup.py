"""Dedup API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.dedup import DedupScan, MergeCandidate
from app.schemas.dedup import DedupScanRead, DedupScanRequest, DedupScanResponse, MergeCandidateRead, MergeCandidateResolve
from app.services.dedup import run_dedup_scan, get_candidates, get_latest_scan, resolve_candidate
from app.services.engagements import resolve_engagement_id

router = APIRouter(prefix="/dedup", tags=["dedup"])


@router.post("/scan", response_model=DedupScanResponse)
def scan_engagement(payload: DedupScanRequest, db: Session = Depends(get_db)):
    engagement_id = resolve_engagement_id(db, None)
    scan = run_dedup_scan(db, engagement_id, threshold=payload.threshold)
    candidates = (
        db.query(MergeCandidate)
        .filter(MergeCandidate.scan_id == scan.id)
        .order_by(MergeCandidate.overall_score.desc())
        .all()
    )
    return DedupScanResponse(
        scan=DedupScanRead.model_validate(scan),
        candidates=[MergeCandidateRead.model_validate(c) for c in candidates],
    )


@router.get("/candidates", response_model=list[MergeCandidateRead])
def list_candidates(status: str | None = None, db: Session = Depends(get_db)):
    engagement_id = resolve_engagement_id(db, None)
    candidates = get_candidates(db, engagement_id, status=status)
    return [MergeCandidateRead.model_validate(c) for c in candidates]


@router.get("/scan/latest", response_model=DedupScanRead | None)
def latest_scan(db: Session = Depends(get_db)):
    engagement_id = resolve_engagement_id(db, None)
    scan = get_latest_scan(db, engagement_id)
    return DedupScanRead.model_validate(scan) if scan else None


@router.post("/candidates/{candidate_id}/resolve", response_model=MergeCandidateRead)
def resolve_merge_candidate(candidate_id: str, payload: MergeCandidateResolve, db: Session = Depends(get_db)):
    try:
        cid = __import__("uuid").UUID(candidate_id)
    except ValueError:
        raise HTTPException(422, "Invalid candidate ID")
    try:
        candidate = resolve_candidate(db, cid, payload.action, payload.notes)
        return MergeCandidateRead.model_validate(candidate)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
