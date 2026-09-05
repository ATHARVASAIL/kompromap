"""AI finding generator.

Turns raw scanner output into a structured, human-readable finding
description suitable for the report. The model sees the finding's
existing fields (title, CWE, CVSS, evidence) and produces a richer
description, remediation steps, and references.

**The tool recommends; the analyst decides.** Generated findings are
advisory output. Nothing here writes to the database — the API returns
the generated content, and the analyst chooses to accept, edit, or
discard it. The same separation triage.py enforces for triage state
applies here for finding content.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from app.models import Finding
from app.schemas.finding_gen import GenerationParseError, GeneratedFinding, parse_generation_response
from app.services.ai.prompts import build_finding_generation_prompt
from app.services.ai.provider import AIProvider, AIResult, get_provider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedFindingResult:
    """One finding's generated content, plus metadata about the call."""

    finding_id: str
    generated: GeneratedFinding | None
    error: str | None = None
    model: str | None = None


def _affected_labels(db: Session, finding: Finding) -> list[str]:
    """Affected assets for this finding."""
    from app.models import Edge, Node
    labels: list[str] = []
    edges = (
        db.query(Edge)
        .filter(Edge.target_node_id == finding.id, Edge.edge_type == "HAS_FINDING")
        .all()
    )
    for e in edges:
        host = db.get(Node, e.source_node_id)
        if host is None:
            continue
        for attr in ("name", "path", "title"):
            value = getattr(host, attr, None)
            if value:
                labels.append(str(value))
                break
    return labels


def generate_finding_description(
    db: Session,
    finding: Finding,
    provider: AIProvider | None = None,
) -> GeneratedFindingResult:
    """Generate a structured description for one finding. Never writes to
    the database."""
    provider = provider or get_provider()

    if not provider.is_configured:
        return GeneratedFindingResult(
            finding_id=str(finding.id),
            generated=None,
            error=provider.complete("", "").failure_message,
        )

    system, user = build_finding_generation_prompt(
        title=finding.title,
        cwe=finding.cwe,
        owasp_category=finding.owasp_category,
        cvss_score=finding.cvss_score,
        cvss_vector=getattr(finding, "cvss_vector", None),
        evidence=finding.evidence,
        affected=_affected_labels(db, finding),
        exploit_public=bool(finding.exploit_public),
        auth_required=bool(finding.auth_required),
    )

    from app.core.config import get_settings

    response = provider.complete(
        system, user, max_tokens=getattr(get_settings(), "ai_max_tokens", 2000)
    )

    if not response.ok:
        return GeneratedFindingResult(
            finding_id=str(finding.id),
            generated=None,
            error=response.failure_message,
            model=response.model,
        )

    try:
        parsed = parse_generation_response(response.text or "")
    except GenerationParseError as exc:
        logger.warning("Finding generation response failed validation: %s", exc)
        return GeneratedFindingResult(
            finding_id=str(finding.id),
            generated=None,
            error="The AI response didn't match the expected format and was discarded.",
            model=response.model,
        )

    return GeneratedFindingResult(
        finding_id=str(finding.id),
        generated=parsed,
        model=response.model,
    )


def generate_findings_batch(
    db: Session,
    finding_ids: Sequence[str],
    provider: AIProvider | None = None,
) -> list[GeneratedFindingResult]:
    """Generate descriptions for multiple findings. Processes each
    independently so one failure doesn't block the rest."""
    import uuid
    results: list[GeneratedFindingResult] = []
    for fid in finding_ids:
        finding = db.get(Finding, uuid.UUID(fid))
        if finding is None:
            results.append(
                GeneratedFindingResult(finding_id=fid, generated=None, error="Finding not found")
            )
            continue
        results.append(generate_finding_description(db, finding, provider))
    return results
