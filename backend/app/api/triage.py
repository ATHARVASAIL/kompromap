"""AI triage endpoints.

Note the shape of the API: `POST /analyze` produces *advice*, and there is
deliberately no endpoint that lets the AI act on a finding. Changing
verification status, severity or anything else still goes through the
existing `PATCH /api/nodes/{id}`, which only an analyst calls. Keeping
that boundary in the API surface — not just in the service layer — means
it can't be eroded by a later convenience endpoint.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Finding
from app.schemas.triage import AITriageResult
from app.services.ai.provider import get_provider
from app.services.ai.triage import load_assessment, store_assessment, triage_finding

router = APIRouter(prefix="/triage", tags=["triage"])


class TriageStatusResponse(BaseModel):
    """Whether AI triage is usable at all, so the UI can explain its
    absence rather than showing a button that always fails."""

    available: bool
    provider: str
    reason: str | None = None


class TriageResponse(BaseModel):
    finding_id: uuid.UUID
    available: bool
    assessment: AITriageResult | None = None
    error: str | None = None
    model: str | None = None
    analyzed_at: str | None = None
    # Restated on every response so a client can't render an assessment
    # without also having been told it's advisory.
    advisory_only: bool = True


@router.get("/status", response_model=TriageStatusResponse)
def triage_status():
    provider = get_provider()
    if provider.is_configured:
        return TriageStatusResponse(available=True, provider=provider.name)
    return TriageStatusResponse(
        available=False,
        provider=provider.name,
        reason=(
            "No AI provider configured. Set ANTHROPIC_API_KEY to enable AI triage — "
            "every other Kompromap feature works without it."
        ),
    )


def _get_finding(db: Session, finding_id: uuid.UUID) -> Finding:
    node = db.get(Finding, finding_id)
    if node is None:
        raise HTTPException(404, "Finding not found")
    return node


@router.post("/findings/{finding_id}/analyze", response_model=TriageResponse)
def analyze_finding(finding_id: uuid.UUID, db: Session = Depends(get_db)):
    """Run AI triage. Produces advice; changes nothing the analyst owns."""
    finding = _get_finding(db, finding_id)
    outcome = triage_finding(db, finding)

    if not outcome.ok:
        # Not an HTTP error — "the AI couldn't help here" is a normal
        # outcome the UI renders inline, not a failed request.
        return TriageResponse(
            finding_id=finding_id, available=False, error=outcome.error, model=outcome.model
        )

    store_assessment(db, finding, outcome)
    return TriageResponse(
        finding_id=finding_id,
        available=True,
        assessment=outcome.result,
        model=outcome.model,
        analyzed_at=outcome.analyzed_at.isoformat() if outcome.analyzed_at else None,
    )


@router.get("/findings/{finding_id}", response_model=TriageResponse)
def get_finding_assessment(finding_id: uuid.UUID, db: Session = Depends(get_db)):
    """Read back a stored assessment without re-running the model."""
    finding = _get_finding(db, finding_id)
    stored = load_assessment(finding)

    if not stored:
        return TriageResponse(
            finding_id=finding_id, available=False, error="This finding has not been analyzed yet."
        )

    meta = stored.pop("_meta", {}) or {}
    try:
        assessment = AITriageResult.model_validate(stored)
    except Exception:
        # Stored data that no longer validates (e.g. after a schema
        # change) is discarded rather than partially rendered.
        return TriageResponse(
            finding_id=finding_id,
            available=False,
            error="The stored assessment is no longer readable. Re-run analysis.",
        )

    return TriageResponse(
        finding_id=finding_id,
        available=True,
        assessment=assessment,
        model=meta.get("model"),
        analyzed_at=meta.get("analyzed_at"),
    )
