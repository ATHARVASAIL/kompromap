"""AI triage orchestration.

Ties provider + prompt + validation together for a single finding.

The one invariant this module enforces, and the reason it's a service
rather than inline in the router: **it never mutates analyst state.** It
writes `ai_assessment` and nothing else. It cannot set
`verification_status`, cannot change `cvss_score`, cannot alter `status`.

That isn't defensive coding for its own sake. An AI that can mark findings
confirmed is an AI that can put a fabricated vulnerability into a client
report, or quietly bury a real one — and it would do so through exactly
the untrusted channel `prompts.py` is defending. Keeping the write surface
to one advisory column means the worst case for a successful injection is
bad advice the analyst reads and rejects.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Edge, Finding, Node
from app.schemas.triage import AITriageResult, TriageParseError, parse_triage_response
from app.services.ai.prompts import build_triage_prompt
from app.services.ai.provider import AIProvider, AIResult, get_provider

logger = logging.getLogger(__name__)


@dataclass
class TriageOutcome:
    """Either a validated assessment or a reason there isn't one.

    Failures are first-class rather than exceptions because "the AI
    couldn't help with this one" is a normal state the UI must render
    honestly, not an error condition.
    """

    result: AITriageResult | None
    error: str | None = None
    model: str | None = None
    analyzed_at: datetime | None = None

    @property
    def ok(self) -> bool:
        return self.result is not None


def _affected_labels(db: Session, finding: Finding) -> list[str]:
    """What this finding was found on — the inverse of HAS_FINDING."""
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


def _source_tool(finding: Finding) -> str | None:
    """Best-effort provenance from the evidence string the parsers write.

    Deliberately best-effort: it's context for the model, not a fact the
    assessment depends on, so a wrong guess costs nothing.
    """
    evidence = (finding.evidence or "").lower()
    for marker, tool in (
        ("curl=", "nuclei"),
        ("matcher=", "nuclei"),
        ("burp", "burp suite"),
        ("zap", "owasp zap"),
        ("nmap", "nmap"),
    ):
        if marker in evidence:
            return tool
    return None


def triage_finding(
    db: Session, finding: Finding, provider: AIProvider | None = None
) -> TriageOutcome:
    """Run AI triage for one finding. Never raises."""
    provider = provider or get_provider()

    if not provider.is_configured:
        # Ask the provider itself rather than constructing a bare AIResult —
        # that path defaulted failure to None and produced the generic
        # "provider returned an error" message instead of the accurate
        # "not configured" one, which sends the analyst looking for a
        # fault that doesn't exist.
        return TriageOutcome(result=None, error=provider.complete("", "").failure_message)

    system, user = build_triage_prompt(
        title=finding.title,
        cwe=finding.cwe,
        owasp_category=finding.owasp_category,
        cvss_score=finding.cvss_score,
        cvss_vector=getattr(finding, "cvss_vector", None),
        evidence=finding.evidence,
        affected=_affected_labels(db, finding),
        source_tool=_source_tool(finding),
        exploit_public=bool(finding.exploit_public),
        auth_required=bool(finding.auth_required),
    )

    from app.core.config import get_settings

    response = provider.complete(
        system, user, max_tokens=getattr(get_settings(), "ai_max_tokens", 2000)
    )

    if not response.ok:
        return TriageOutcome(result=None, error=response.failure_message, model=response.model)

    try:
        parsed = parse_triage_response(response.text or "")
    except TriageParseError as exc:
        # The model replied with something unusable. Log the detail
        # server-side; the analyst gets a plain statement, not a parser
        # error, because there's nothing they can act on in it.
        logger.warning("AI triage response failed validation: %s", exc)
        return TriageOutcome(
            result=None,
            error="The AI response didn't match the expected format and was discarded.",
            model=response.model,
        )

    return TriageOutcome(
        result=parsed,
        model=response.model,
        analyzed_at=datetime.now(timezone.utc),
    )


def store_assessment(db: Session, finding: Finding, outcome: TriageOutcome) -> None:
    """Persist an assessment as advisory metadata.

    Writes `ai_assessment` only. Deliberately does not touch
    `verification_status`, `status`, `cvss_score` or any other analyst-
    owned field — see the module docstring.
    """
    if not outcome.ok or outcome.result is None:
        return

    finding.ai_assessment = json.dumps(
        {
            **outcome.result.model_dump(mode="json"),
            "_meta": {
                "model": outcome.model,
                "analyzed_at": outcome.analyzed_at.isoformat() if outcome.analyzed_at else None,
                # Recorded so the UI can always caption the assessment as
                # advisory, even if that framing is lost elsewhere.
                "advisory_only": True,
            },
        }
    )
    db.commit()


def load_assessment(finding: Finding) -> dict | None:
    """Read a stored assessment back, tolerating corruption."""
    raw = getattr(finding, "ai_assessment", None)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError):
        logger.warning("Stored ai_assessment for finding %s is not valid JSON", finding.id)
        return None
