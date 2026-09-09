"""Correlation API endpoints (Phase 3)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.dashboard import CorrelationResponse
from app.services.correlation import compute_correlation_matrix
from app.services.engagements import resolve_engagement_id

router = APIRouter(prefix="/correlation", tags=["correlation"])


@router.get("", response_model=CorrelationResponse)
def get_correlation(db: Session = Depends(get_db)):
    engagement_id = resolve_engagement_id(db, None)
    return compute_correlation_matrix(db, engagement_id)
