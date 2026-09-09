"""Deduplication engine — similarity scoring across findings within an engagement.

The analyst approves every merge. Nothing is auto-merged.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.dedup import DedupScan, MergeCandidate
from app.models.edge import Edge, EdgeType
from app.models.node import Endpoint, Finding, Node


# ---------------------------------------------------------------------------
# Thresholds (configurable per-scan, these are defaults)
# ---------------------------------------------------------------------------
DEFAULT_OVERALL_THRESHOLD = 0.75
HIGH_CONFIDENCE_THRESHOLD = 0.85

# Dimension weights that produce the composite overall_score
DIMENSION_WEIGHTS = {
    "url_similarity": 0.20,
    "endpoint_similarity": 0.25,
    "param_similarity": 0.15,
    "cwe_similarity": 0.20,
    "request_similarity": 0.10,
    "response_similarity": 0.10,
}

# Fields that constitute a "high-impact" finding — these must never be
# auto-merged.  The UI hides the auto-merge button for pairs where either
# finding is above these thresholds.
HIGH_IMPACT_CVSS = 7.0
HIGH_IMPACT_HAS_POC = True  # exploit_public == True


@dataclass
class FindingContext:
    """Enriched data about a finding needed for similarity scoring."""
    finding_id: UUID
    title: str
    cwe: str | None
    cvss_score: float | None
    exploit_public: bool
    evidence: str | None
    # Associated endpoint path/method (if any)
    endpoint_path: str | None
    endpoint_method: str | None
    endpoint_params: list[str] = field(default_factory=list)
    # Associated asset name (if any)
    asset_name: str | None
    asset_tags: list[str] = field(default_factory=list)
    # URL if the finding references one
    url: str | None


def _normalize_url(raw: str | None) -> str | None:
    if not raw:
        return None
    # Strip protocol, www., trailing slash, query string for comparison
    u = raw.strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = re.sub(r"/+$", "", u)
    u = re.sub(r"\?.*$", "", u)
    return u


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens, dropping punctuation."""
    return re.findall(r"\b[a-z0-9_]+\b", text.lower())


def _similarity_ratio(a: str, b: str) -> float:
    """Return 0-1 similarity between two strings using SequenceMatcher."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _jaccard(a: list[str], b: list[str]) -> float:
    """Jaccard index on token sets."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _extract_json_blocks(text: str | None) -> list[dict[str, Any]]:
    """Try to extract JSON objects from free-text evidence."""
    if not text:
        return []
    blocks: list[dict[str, Any]] = []
    for m in re.finditer(r"\{[^{}]*\}", text):
        try:
            blocks.append(json.loads(m.group()))
        except json.JSONDecodeError:
            continue
    return blocks


def _normalize_json(obj: Any) -> str:
    """Canonical JSON string for comparison — sorts keys, strips whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def score_dimensions(a: FindingContext, b: FindingContext) -> dict[str, float]:
    """Compute per-dimension similarity scores (0-1 each)."""
    # --- URL similarity ---
    url_sim = _similarity_ratio(
        _normalize_url(a.url), _normalize_url(b.url)
    )

    # --- Endpoint similarity (method + path) ---
    ep_sim = 0.0
    if a.endpoint_path and b.endpoint_path:
        ep_sim = _similarity_ratio(
            f"{a.endpoint_method or ''}:{a.endpoint_path}",
            f"{b.endpoint_method or ''}:{b.endpoint_path}",
        )
    elif a.endpoint_path == b.endpoint_path is None:
        ep_sim = 1.0

    # --- Parameter similarity ---
    param_sim = _jaccard(a.endpoint_params, b.endpoint_params)

    # --- CWE similarity ---
    cwe_sim = 1.0 if (a.cwe and b.cwe and a.cwe == b.cwe) else 0.0

    # --- Request body similarity ---
    req_a = _extract_json_blocks(a.evidence)
    req_b = _extract_json_blocks(b.evidence)
    if req_a and req_b:
        # Compare the first JSON block from each
        ra, rb = _normalize_json(req_a[0]), _normalize_json(req_b[0])
        req_sim = _similarity_ratio(ra, rb)
    else:
        # Fall back to title overlap
        req_sim = _similarity_ratio(a.title, b.title) * 0.5

    # --- Response / output similarity ---
    # Use the evidence text after stripping JSON — what remains is free-form
    # response / remediation text.
    resp_a = re.sub(r"\{[^{}]*\}", "", a.evidence or "")
    resp_b = re.sub(r"\{[^{}]*\}", "", b.evidence or "")
    resp_tokens_a = _tokenize(resp_a)
    resp_tokens_b = _tokenize(resp_b)
    resp_sim = _jaccard(resp_tokens_a, resp_tokens_b)

    return {
        "url_similarity": round(url_sim, 4),
        "endpoint_similarity": round(ep_sim, 4),
        "param_similarity": round(param_sim, 4),
        "cwe_similarity": round(cwe_sim, 4),
        "request_similarity": round(req_sim, 4),
        "response_similarity": round(resp_sim, 4),
    }


def composite_score(dims: dict[str, float]) -> float:
    """Weighted average of dimension scores."""
    total = 0.0
    wsum = 0.0
    for key, weight in DIMENSION_WEIGHTS.items():
        total += dims.get(key, 0.0) * weight
        wsum += weight
    return round(total / wsum, 4) if wsum else 0.0


def _finding_context(db: Session, finding: Finding) -> FindingContext:
    """Collect all context needed to score a finding."""
    # Find associated endpoint via HAS_FINDING -> Endpoint
    ep_path: str | None = None
    ep_method: str | None = None
    ep_params: list[str] = []
    asset_name: str | None = None
    asset_tags: list[str] = []
    url: str | None = None

    # Walk from finding -> HAS_FINDING edge target
    stmt = (
        select(Edge.source_node_id, Edge.target_node_id)
        .where(and_(Edge.target_node_id == finding.id, Edge.edge_type == EdgeType.HAS_FINDING.value))
    )
    has_finding_targets = [row.source_node_id for row in db.execute(stmt)]

    for target_id in has_finding_targets:
        target_node = db.get(Node, target_id)
        if target_node is None:
            continue
        if isinstance(target_node, Endpoint):
            ep_path = target_node.path
            ep_method = target_node.method
            ep_params = target_node.params or []
            # Base URL from parent WebApplication
            parent_ep = (
                select(Edge.source_node_id)
                .where(and_(Edge.target_node_id == target_node.id, Edge.edge_type == EdgeType.EXPOSES.value))
                .limit(1)
            )
            parent_rows = db.execute(parent_ep).fetchall()
            if parent_rows:
                parent = db.get(Node, parent_rows[0][0])
                if parent:
                    url = f"{parent.notes or ''}{ep_path}" if hasattr(parent, "notes") else ep_path
        elif hasattr(target_node, "name"):
            asset_name = target_node.name  # type: ignore[attr-defined]
            asset_tags = getattr(target_node, "tags", []) or []

    return FindingContext(
        finding_id=finding.id,
        title=finding.title,
        cwe=finding.cwe,
        cvss_score=finding.cvss_score or 0.0,
        exploit_public=finding.exploit_public,
        evidence=finding.evidence,
        endpoint_path=ep_path,
        endpoint_method=ep_method,
        endpoint_params=ep_params,
        asset_name=asset_name,
        asset_tags=asset_tags,
        url=url,
    )


def _is_high_impact(ctx: FindingContext) -> bool:
    return (ctx.cvss_score or 0) >= HIGH_IMPACT_CVSS or ctx.exploit_public == HIGH_IMPACT_HAS_POC


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_dedup_scan(db: Session, engagement_id: UUID, threshold: float = DEFAULT_OVERALL_THRESHOLD) -> DedupScan:
    """Run a full dedup scan for all findings in an engagement.

    Returns the DedupScan record (caller should refresh from DB).
    """
    # Clean up any previous pending candidates for this engagement
    db.execute(
        MergeCandidate.__table__.delete().where(
            and_(MergeCandidate.engagement_id == engagement_id, MergeCandidate.status == "pending")
        )
    )
    db.flush()

    # Fetch all findings for the engagement
    findings_stmt = (
        select(Finding)
        .join(Node, Finding.id == Node.id)
        .where(and_(Node.engagement_id == engagement_id, Node.node_type == "finding"))
    )
    findings: list[Finding] = list(db.execute(findings_stmt).scalars().all())

    contexts: dict[UUID, FindingContext] = {}
    for f in findings:
        contexts[f.id] = _finding_context(db, f)

    # Build candidates — compare every unordered pair
    scan = DedupScan(
        engagement_id=engagement_id,
        total_candidates=0,
        high_confidence_count=0,
        settings_snapshot=json.dumps({
            "threshold": threshold,
            "weights": DIMENSION_WEIGHTS,
        }),
    )
    db.add(scan)
    db.flush()

    high_conf = 0
    candidates = []

    for i in range(len(findings)):
        for j in range(i + 1, len(findings)):
            fa, fb = findings[i], findings[j]
            ca, cb = contexts[fa.id], contexts[fb.id]

            # Never flag as duplicate if either is high-impact (needs analyst review)
            if _is_high_impact(ca) or _is_high_impact(cb):
                continue

            dims = score_dimensions(ca, cb)
            overall = composite_score(dims)

            if overall < threshold:
                continue

            if overall >= HIGH_CONFIDENCE_THRESHOLD:
                high_conf += 1

            candidates.append(
                MergeCandidate(
                    scan_id=scan.id,
                    engagement_id=engagement_id,
                    finding_a_id=fa.id,
                    finding_b_id=fb.id,
                    **dims,
                    overall_score=overall,
                    threshold_used=threshold,
                )
            )

    for c in candidates:
        db.add(c)

    scan.total_candidates = len(candidates)
    scan.high_confidence_count = high_conf
    db.commit()
    db.refresh(scan)
    return scan


def resolve_candidate(db: Session, candidate_id: UUID, action: str, notes: str | None = None) -> MergeCandidate:
    """Resolve a merge candidate: 'merged' or 'dismissed'.

    'merged' = analyst confirms they are the same finding (keep finding_a, discard finding_b).
    'dismissed' = analyst confirms they are different.
    """
    candidate: MergeCandidate | None = db.get(MergeCandidate, candidate_id)
    if candidate is None:
        raise ValueError(f"MergeCandidate {candidate_id} not found")
    if candidate.status != "pending":
        raise ValueError(f"Candidate already resolved as {candidate.status}")

    candidate.status = action
    candidate.notes = notes
    candidate.resolved_at = datetime.utcnow()

    # Update scan counters
    scan: DedupScan | None = db.get(DedupScan, candidate.scan_id)
    if scan:
        if action == "merged":
            scan.merged_count += 1
        else:
            scan.dismissed_count += 1

    if action == "merged":
        # Mark finding_b as merged (move to a different finding in real use)
        # For now we tag the finding as merged via verification_status
        finding_b = db.get(Finding, candidate.finding_b_id)
        if finding_b and finding_b.verification_status == "unverified":
            finding_b.verification_status = "false_positive"

    db.commit()
    db.refresh(candidate)
    return candidate


def get_candidates(db: Session, engagement_id: UUID, status: str | None = None) -> list[MergeCandidate]:
    """List merge candidates for an engagement, optionally filtered by status."""
    stmt = (
        select(MergeCandidate)
        .where(MergeCandidate.engagement_id == engagement_id)
        .order_by(MergeCandidate.overall_score.desc())
    )
    if status:
        stmt = stmt.where(MergeCandidate.status == status)
    return list(db.execute(stmt).scalars().all())


def get_latest_scan(db: Session, engagement_id: UUID) -> DedupScan | None:
    """Most recent dedup scan for an engagement."""
    stmt = (
        select(DedupScan)
        .where(DedupScan.engagement_id == engagement_id)
        .order_by(DedupScan.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
