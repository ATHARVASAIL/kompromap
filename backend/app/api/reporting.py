"""Reporting endpoints (spec §5 Phase 3 / §7 Phase 5)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Engagement
from app.schemas.reporting import (
    ChainRequest,
    EngagementReportRequest,
    EngagementReportResponse,
    ExportRequest,
    ExportResponse,
    NarrativeResponse,
)
from app.services.engagement_report import build_engagement_report
from app.services.engagements import resolve_engagement_id
import base64

from app.services.report_render import render_html, render_json, render_report_markdown
from app.services.reporting import (
    ChainResolutionError,
    build_chain_export,
    generate_narrative,
    render_markdown,
    resolve_chain,
)
from app.services.scoring import DEFAULT_WEIGHTS, ScoringWeights

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

    fmt = payload.format
    if fmt == "markdown":
        content = render_markdown(steps, narrative)
        return ExportResponse(format="markdown", narrative_source="llm" if used_llm else "template", content=content)

    if fmt == "docx":
        from app.services.report_export import render_report_docx
        raw = build_chain_export(steps, narrative, used_llm)
        return ExportResponse(
            format="docx",
            narrative_source="llm" if used_llm else "template",
            content_b64=base64.b64encode(render_report_docx(raw)).decode(),
            filename=f"chain-export.docx",
        )

    if fmt == "pdf":
        from app.services.report_export import render_report_pdf
        raw = build_chain_export(steps, narrative, used_llm)
        return ExportResponse(
            format="pdf",
            narrative_source="llm" if used_llm else "template",
            content_b64=base64.b64encode(render_report_pdf(raw)).decode(),
            filename=f"chain-export.pdf",
        )

    data = build_chain_export(steps, narrative, used_llm)
    return ExportResponse(format="json", narrative_source="llm" if used_llm else "template", data=data)


@router.post("/engagement", response_model=EngagementReportResponse)
def engagement_report(payload: EngagementReportRequest, db: Session = Depends(get_db)):
    engagement_id = resolve_engagement_id(db, payload.engagement_id)
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, "Engagement not found")
    weights = (
        ScoringWeights(**payload.weights.model_dump(exclude_none=True))
        if payload.weights
        else DEFAULT_WEIGHTS
    )
    report = build_engagement_report(db, engagement, weights, include_narratives=payload.include_narratives)
    fmt = payload.format
    if fmt == "markdown":
        return EngagementReportResponse(format="markdown", content=render_report_markdown(report))
    if fmt == "html":
        return EngagementReportResponse(format="html", content=render_html(report))
    if fmt == "docx":
        from app.services.report_export import render_report_docx
        raw = render_json(report)
        return EngagementReportResponse(
            format="docx",
            content_b64=base64.b64encode(render_report_docx(raw)).decode(),
            filename=f"{report.get('engagement_name', 'engagement')}.docx",
        )
    if fmt == "pdf":
        from app.services.report_export import render_report_pdf
        raw = render_json(report)
        return EngagementReportResponse(
            format="pdf",
            content_b64=base64.b64encode(render_report_pdf(raw)).decode(),
            filename=f"{report.get('engagement_name', 'engagement')}.pdf",
        )
    return EngagementReportResponse(format="json", data=render_json(report))
