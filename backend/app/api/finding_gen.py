"""AI finding generation endpoints.

The endpoint produces structured descriptions for existing findings.
It never writes to the database — generated content is advisory output
returned to the analyst, who chooses to accept, edit, or discard it.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Finding
from app.schemas.finding_gen import GeneratedFinding
from app.services.ai.finding_generator import generate_finding_description
from app.services.ai.provider import get_provider

router = APIRouter(prefix="/finding-gen", tags=["finding-generation"])


class FindingGenRequest(BaseModel):
    finding_id: uuid.UUID | None = None
    finding_ids: list[uuid.UUID] | None = None


class FindingGenResponse(BaseModel):
    finding_id: str
    available: bool
    generated: GeneratedFinding | None = None
    error: str | None = None
    model: str | None = None


class FindingGenStatusResponse(BaseModel):
    available: bool
    provider: str
    reason: str | None = None


@router.get("/status", response_model=FindingGenStatusResponse)
def get_status():
    provider = get_provider()
    return FindingGenStatusResponse(
        available=provider.is_configured,
        provider=provider.name,
        reason=None if provider.is_configured else provider.complete("", "").failure_message,
    )


@router.post("/generate", response_model=FindingGenResponse)
def generate_for_finding(
    payload: FindingGenRequest,
    db: Session = Depends(get_db),
):
    provider = get_provider()
    if not provider.is_configured:
        raise HTTPException(
            503,
            detail=provider.complete("", "").failure_message or "AI provider not configured",
        )

    if not payload.finding_id:
        raise HTTPException(422, detail="finding_id is required")

    finding = db.get(Finding, payload.finding_id)
    if finding is None:
        raise HTTPException(404, detail="Finding not found")

    result = generate_finding_description(db, finding, provider)
    return FindingGenResponse(
        finding_id=result.finding_id,
        available=True,
        generated=result.generated,
        error=result.error,
        model=result.model,
    )
