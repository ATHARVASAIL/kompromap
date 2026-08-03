"""Reporting endpoints (spec §5 Phase 3 / §7 Phase 5): narrative generation
for a selected chain, and exporting it as Markdown or JSON.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Engagement
from app.services.engagement_report import build_engagement_report
from app.services.engagements import resolve_engagement_id
from app.services.report_render import (
    render_html,
    render_json,
    render_markdown as render_report_markdown,
)
from app.services.scoring import DEFAULT_WEIGHTS, ScoringWeights
from app.schemas.reporting import (
    ChainRequest,
    EngagementReportRequest,
    EngagementReportResponse,
    ExportRequest,
    ExportResponse,
    NarrativeResponse,
)
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


@router.post("/engagement", response_model=EngagementReportResponse)
def engagement_report(
    payload: EngagementReportRequest,
    db: Session = Depends(get_db),
):
    """Full engagement report — every finding, every chain, scope inventory,
    prioritised remediation and the report's own caveats.

    `format` picks the deliverable:
      * `json`     — structured, for further processing
      * `markdown` — paste into an existing report template
      * `html`     — self-contained page that prints straight to PDF
    """
    engagement_id = resolve_engagement_id(db, payload.engagement_id)
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, "Engagement not found")

    weights = (
        ScoringWeights(**payload.weights.model_dump(exclude_none=True))
        if payload.weights
        else DEFAULT_WEIGHTS
    )

    report = build_engagement_report(
        db, engagement, weights, include_narratives=payload.include_narratives
    )

    if payload.format == "markdown":
        return EngagementReportResponse(
            format="markdown", content=render_report_markdown(report)
        )
    if payload.format == "html":
        return EngagementReportResponse(format="html", content=render_html(report))
    return EngagementReportResponse(format="json", data=render_json(report))
