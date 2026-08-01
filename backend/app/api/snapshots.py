"""Snapshot endpoints — spec §5 Phase 4 / §7 Phase 6: capture a point-in-
time copy of an engagement's graph, and diff it against the current state
(or another snapshot) later.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Engagement, Snapshot
from app.schemas.snapshot import GraphDiff, SnapshotCreate, SnapshotDetail, SnapshotSummary
from app.services.snapshots import create_snapshot, diff_snapshot

router = APIRouter(tags=["snapshots"])


def _get_engagement_or_404(db: Session, engagement_id: uuid.UUID) -> Engagement:
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, "Engagement not found")
    return engagement


@router.post("/engagements/{engagement_id}/snapshots", response_model=SnapshotSummary, status_code=201)
def create_engagement_snapshot(
    engagement_id: uuid.UUID, payload: SnapshotCreate, db: Session = Depends(get_db)
):
    _get_engagement_or_404(db, engagement_id)
    snapshot = create_snapshot(db, engagement_id, payload.label)
    return SnapshotSummary.model_validate(snapshot)


@router.get("/engagements/{engagement_id}/snapshots", response_model=list[SnapshotSummary])
def list_engagement_snapshots(engagement_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_engagement_or_404(db, engagement_id)
    snapshots = db.scalars(
        select(Snapshot).where(Snapshot.engagement_id == engagement_id).order_by(Snapshot.created_at.desc())
    )
    return [SnapshotSummary.model_validate(s) for s in snapshots]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotDetail)
def get_snapshot(snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    snapshot = db.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(404, "Snapshot not found")
    return SnapshotDetail.model_validate(snapshot)


@router.get("/snapshots/{snapshot_id}/diff", response_model=GraphDiff)
def diff_snapshot_endpoint(
    snapshot_id: uuid.UUID,
    compare_to: uuid.UUID | None = Query(
        default=None, description="Another snapshot to diff against. Defaults to the current live graph."
    ),
    db: Session = Depends(get_db),
):
    base = db.get(Snapshot, snapshot_id)
    if base is None:
        raise HTTPException(404, "Snapshot not found")

    compare_snapshot = None
    if compare_to is not None:
        compare_snapshot = db.get(Snapshot, compare_to)
        if compare_snapshot is None:
            raise HTTPException(404, "compare_to snapshot not found")

    diff = diff_snapshot(db, base, compare_snapshot)
    return GraphDiff.model_validate(diff)


@router.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot(snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    snapshot = db.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(404, "Snapshot not found")
    db.delete(snapshot)
    db.commit()
