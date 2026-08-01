"""Reporting endpoints (spec §5 Phase 3 / §7 Phase 5): narrative generation
for a selected chain, and exporting it as Markdown or JSON.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.reporting import ChainRequest, ExportRequest, ExportResponse, NarrativeResponse
from app.services.reporting import (
    ChainResolutionError,
    build_chain_export,
    generate_narrative,
    render_markdown,
    resolve_chain,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/narrative", response_model=NarrativeResponse)
def create_narrative(payload: ChainRequest, db: Session = Depends(get_db)):
    try:
        steps = resolve_chain(db, payload.node_ids)
    except ChainResolutionError as e:
        raise HTTPException(422, str(e)) from e

    narrative, used_llm = generate_narrative(steps)
    return NarrativeResponse(narrative=narrative, narrative_source="llm" if used_llm else "template")


@router.post("/export", response_model=ExportResponse)
def export_chain(payload: ExportRequest, db: Session = Depends(get_db)):
    try:
        steps = resolve_chain(db, payload.node_ids)
    except ChainResolutionError as e:
        raise HTTPException(422, str(e)) from e

    if payload.narrative:
        narrative, used_llm = payload.narrative, False
    else:
        narrative, used_llm = generate_narrative(steps)

    if payload.format == "markdown":
        content = render_markdown(steps, narrative)
        return ExportResponse(
            format="markdown",
            narrative_source="llm" if used_llm else "template",
            content=content,
        )

    data = build_chain_export(steps, narrative, used_llm)
    return ExportResponse(
        format="json",
        narrative_source="llm" if used_llm else "template",
        data=data,
    )
