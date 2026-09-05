"""Deduplication engine — similarity scoring and merge candidate generation.

Scans all finding pairs within an engagement, scores them across multiple
signals (title, CWE, OWASP, URL/location, endpoint path, parameters),
and surfaces pairs above a configurable threshold as MergeCandidates for
the analyst to review.

The analyst decides. The tool never auto-merges. High-impact findings
(CVSS >= 7.0 on either side) require explicit analyst approval for any
merge action.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher


from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Asset, Edge, EdgeType, Endpoint, Finding, Node, NodeType, Service, WebApplication
from app.models.dedup import DedupScan, MergeCandidate
from app.models.enums import FindingStatus, NodeType as NodeTypeEnum


# ---------------------------------------------------------------------------
# Signal weights — how much each dimension contributes to the overall score.
# Configurable per-scan; these are sensible defaults.
# ---------------------------------------------------------------------------
DEFAULT_SIGNAL_WEIGHTS: dict[str, float] = {
    "title": 0.25,
    "cwe": 0.25,
    "owasp": 0.10,
    "location": 0.20,
    "endpoint": 0.12,
    "params": 0.08,
}

# Findings at or above this CVSS are "high impact" — merges touching them
# must be explicitly approved by the analyst.
HIGH_IMPACT_THRESHOLD = 7.0


# ---------------------------------------------------------------------------
# Context: one dict per finding, gathered once per scan.
# ---------------------------------------------------------------------------
@dataclass
class FindingContext:
    """Everything the dedup engine needs to compare two findings."""

    id: uuid.UUID
    title: str
    cwe: str | None
    owasp: str | None
    cvss_score: float | None
    # Normalized location string: full URL if available, asset name otherwise.
    location: str
    # Normalized endpoint path (params collapsed to {param}) or empty string.
    endpoint_path: str
    # Sorted parameter names.
    params: list[str]


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip surrounding punctuation."""
    import re
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s/{}.-]", "", text)
    return text


def _normalize_path(path: str) -> str:
    """Collapse path parameters so /users/123 and /users/456 both become /users/{id}."""
    import re
    path = _normalize(path)
    # Collapse numeric segments
    path = re.sub(r"/\d+", "/{id}", path)
    # Collapse common non-numeric param patterns
    path = re.sub(r"/[a-f0-9]{8,}", "/{token}", path)
    return path


def _get_has_finding_sources(db: Session, finding_id: uuid.UUID) -> list[Node]:
    """Return the source nodes of HAS_FINDING edges pointing at this finding."""
    edges = db.scalars(
        select(Edge).where(
            and_(
                Edge.target_node_id == finding_id,
                Edge.edge_type == EdgeType.HAS_FINDING.value,
            )
        )
    ).all()
    sources = []
    for edge in edges:
        node = db.get(Node, edge.source_node_id)
        if node is not None:
            sources.append(node)
    return sources


def _build_url_for_endpoint(db: Session, endpoint: Endpoint) -> str:
    """Walk Asset → Service → WebApplication to reconstruct the base URL."""
    # Find the asset hosting this endpoint via EXPOSES edges.
    exposer_edges = db.scalars(
        select(Edge).where(
            and_(
                Edge.target_node_id == endpoint.id,
                Edge.edge_type == EdgeType.EXPOSES.value,
            )
        )
    ).all()
    for ee in exposer_edges:
        service = db.get(Service, ee.source_node_id)
        if service is None:
            continue
        # Find web apps on this service via EXPOSES (or EXPOSES from service to web_app)
        # Actually, EXPOSES goes Service → Endpoint or Service → WebApplication.
        # Let me look for HOSTS edges to find the asset, then find web apps.
        host_edges = db.scalars(
            select(Edge).where(
                and_(
                    Edge.target_node_id == service.id,
                    Edge.edge_type == EdgeType.HOSTS.value,
                )
            )
        ).all()
        for he in host_edges:
            asset = db.get(Asset, he.source_node_id)
            if asset is None:
                continue
            # Find web apps on this asset (via service HOSTS)
            web_apps = _find_web_apps_on_asset(db, asset.id)
            if web_apps:
                # Use the first web app's base_url + endpoint path
                base = web_apps[0].base_url.rstrip("/")
                return f"{base}{endpoint.path}"
    # Fallback: just the endpoint path
    return endpoint.path


def _find_web_apps_on_asset(db: Session, asset_id: uuid.UUID) -> list[WebApplication]:
    """Find WebApplications reachable from an asset via HOSTS → EXPOSES."""
    # Find services hosted on this asset (HOSTS: Asset → Service)
    service_edges = db.scalars(
        select(Edge).where(
            and_(
                Edge.source_node_id == asset_id,
                Edge.edge_type == EdgeType.HOSTS.value,
            )
        )
    ).all()
    web_apps: list[WebApplication] = []
    for se in service_edges:
        service = db.get(Service, se.target_node_id)
        if service is None:
            continue
        # Find web apps exposed by this service
        expose_edges = db.scalars(
            select(Edge).where(
                and_(
                    Edge.source_node_id == service.id,
                    Edge.edge_type == EdgeType.EXPOSES.value,
                )
            )
        ).all()
        for ee in expose_edges:
            wa = db.get(WebApplication, ee.target_node_id)
            if wa is not None:
                web_apps.append(wa)
    return web_apps


def _build_finding_context(db: Session, finding: Finding) -> FindingContext:
    """Gather all signals needed to compare this finding against others."""
    sources = _get_has_finding_sources(db, finding.id)

    location = ""
    endpoint_path = ""
    params: list[str] = []

    for source in sources:
        if source.node_type == NodeTypeEnum.ENDPOINT.value:
            ep = db.get(Endpoint, source.id)
            if ep is not None:
                endpoint_path = _normalize_path(ep.path)
                params = sorted(ep.params or [])
                location = _build_url_for_endpoint(db, ep)
                break
        elif source.node_type == NodeTypeEnum.ASSET.value:
            asset = db.get(Asset, source.id)
            if asset is not None:
                location = _normalize(asset.name)
                # If the asset has associated web apps, prefer those URLs.
                web_apps = _find_web_apps_on_asset(db, asset.id)
                if web_apps:
                    # Build a generic URL from the first web app + asset name
                    # (we don't have an endpoint here, so just the base)
                    location = _normalize(web_apps[0].base_url)
                    # Also try to find endpoints under this asset for path info
                    for ep_edge in db.scalars(
                        select(Edge).where(
                            and_(
                                Edge.source_node_id == asset.id,
                                Edge.edge_type == EdgeType.EXPOSES.value,
                            )
                        )
                    ).all():
                        ep = db.get(Endpoint, ep_edge.target_node_id)
                        if ep is not None:
                            endpoint_path = _normalize_path(ep.path)
                            params = sorted(ep.params or [])
                            break

    return FindingContext(
        id=finding.id,
        title=_normalize(finding.title),
        cwe=(finding.cwe or "").strip().lower(),
        owasp=(finding.owasp_category or "").strip().lower(),
        cvss_score=finding.cvss_score,
        location=location,
        endpoint_path=endpoint_path,
        params=params,
    )


# ---------------------------------------------------------------------------
# Signal scorers — each returns 0.0–1.0 for a pair of contexts.
# ---------------------------------------------------------------------------

def _score_title(a: FindingContext, b: FindingContext) -> float:
    """String similarity on normalized titles."""
    return float(SequenceMatcher(None, a.title, b.title).ratio())


def _score_cwe(a: FindingContext, b: FindingContext) -> float:
    """Exact CWE match, or 0.0 if either is missing or different."""
    if not a.cwe or not b.cwe:
        return 0.0
    return 1.0 if a.cwe == b.cwe else 0.0


def _score_owasp(a: FindingContext, b: FindingContext) -> float:
    """Exact OWASP category match, or 0.0 if either is missing or different."""
    if not a.owasp or not b.owasp:
        return 0.0
    return 1.0 if a.owasp == b.owasp else 0.0


def _score_location(a: FindingContext, b: FindingContext) -> float:
    """Similarity on the location string (URL or asset name)."""
    if not a.location or not b.location:
        return 0.0
    return float(SequenceMatcher(None, a.location, b.location).ratio())


def _score_endpoint(a: FindingContext, b: FindingContext) -> float:
    """Similarity on the normalized endpoint path."""
    if not a.endpoint_path or not b.endpoint_path:
        return 0.0
    return float(SequenceMatcher(None, a.endpoint_path, b.endpoint_path).ratio())


def _score_params(a: FindingContext, b: FindingContext) -> float:
    """Jaccard overlap of parameter name sets."""
    if not a.params and not b.params:
        return 0.0
    set_a, set_b = set(a.params), set(b.params)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


_SIGNAL_SCORERS: dict[str, callable] = {
    "title": _score_title,
    "cwe": _score_cwe,
    "owasp": _score_owasp,
    "location": _score_location,
    "endpoint": _score_endpoint,
    "params": _score_params,
}


def _score_pair(
    a: FindingContext, b: FindingContext,
    weights: dict[str, float],
) -> tuple[float, dict[str, float]]:
    """Compute weighted similarity between two findings.

    Returns (overall_score, per_signal_scores).
    """
    signal_scores: dict[str, float] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for signal, weight in weights.items():
        scorer = _SIGNAL_SCORERS.get(signal)
        if scorer is None:
            continue
        score = scorer(a, b)
        signal_scores[signal] = round(score, 4)
        weighted_sum += score * weight
        total_weight += weight

    overall = weighted_sum / total_weight if total_weight > 0 else 0.0
    return round(overall, 4), signal_scores


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_scan(
    db: Session,
    engagement_id: uuid.UUID,
    threshold: float = 0.5,
    signals: list[str] | None = None,
    weights: dict[str, float] | None = None,
) -> DedupScan:
    """Run dedup across all findings in an engagement.

    Parameters
    ----------
    engagement_id : uuid.UUID
        The engagement to scan.
    threshold : float
        Minimum overall score (0.0–1.0) for a pair to surface as a candidate.
    signals : list[str] | None
        Which signal dimensions to use. Defaults to all available signals.
    weights : dict[str, float] | None
        Per-signal weights. Must sum > 0; defaults to DEFAULT_SIGNAL_WEIGHTS.

    Returns
    -------
    DedupScan
        The scan record, with candidates populated.
    """
    active_signals = signals or list(DEFAULT_SIGNAL_WEIGHTS.keys())
    active_weights = weights or dict(DEFAULT_SIGNAL_WEIGHTS)
    # Normalize weights to sum to 1.0
    total_w = sum(active_weights.get(s, 0.0) for s in active_signals)
    if total_w <= 0:
        raise ValueError("Signal weights must sum to a positive number")
    active_weights = {s: w / total_w for s, w in active_weights.items() if s in active_signals}

    # Fetch all findings for this engagement.
    findings = list(
        db.scalars(
            select(Finding).where(Finding.engagement_id == engagement_id)
        )
    )

    if len(findings) < 2:
        # Nothing to compare.
        scan = DedupScan(
            engagement_id=engagement_id,
            similarity_threshold=threshold,
            signals=active_signals,
            candidates_found=0,
            candidates_filtered=0,
        )
        db.add(scan)
        db.commit()
        return scan

    # Build context for every finding (one query per finding for sources).
    contexts: dict[uuid.UUID, FindingContext] = {}
    for f in findings:
        contexts[f.id] = _build_finding_context(db, f)

    # Compare all pairs. O(n^2) but engagement-scale is hundreds, not millions.
    candidates_created = 0
    candidates_filtered = 0
    candidate_rows: list[MergeCandidate] = []

    for i in range(len(findings)):
        for j in range(i + 1, len(findings)):
            fa, fb = findings[i], findings[j]
            ca, cb = contexts[fa.id], contexts[fb.id]

            overall, signal_scores = _score_pair(ca, cb, active_weights)

            if overall < threshold:
                candidates_filtered += 1
                continue

            high_impact = (
                (fa.cvss_score or 0.0) >= HIGH_IMPACT_THRESHOLD
                or (fb.cvss_score or 0.0) >= HIGH_IMPACT_THRESHOLD
            )

            candidate_rows.append(
                MergeCandidate(
                    finding_a_id=fa.id,
                    finding_b_id=fb.id,
                    signal_scores=signal_scores,
                    overall_score=overall,
                    high_impact=high_impact,
                    action="pending",
                )
            )
            candidates_created += 1

    # Create scan first, flush to get the ID, then bulk-create candidates
    # with the scan_id already set. Avoids the unreliable db.new walk.
    scan = DedupScan(
        engagement_id=engagement_id,
        similarity_threshold=threshold,
        signals=active_signals,
        candidates_found=candidates_created,
        candidates_filtered=candidates_filtered,
    )
    db.add(scan)
    db.flush()  # get scan.id without committing

    for row in candidate_rows:
        row.scan_id = scan.id
        db.add(row)

    db.commit()
    return scan


def get_scan(db: Session, scan_id: uuid.UUID) -> DedupScan | None:
    """Retrieve a scan by ID, with its candidates eagerly loaded."""
    return db.get(DedupScan, scan_id)


def get_scans_for_engagement(
    db: Session, engagement_id: uuid.UUID, limit: int = 20
) -> list[DedupScan]:
    """List recent scans for an engagement, newest first."""
    stmt = (
        select(DedupScan)
        .where(DedupScan.engagement_id == engagement_id)
        .order_by(DedupScan.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_candidates_for_scan(
    db: Session, scan_id: uuid.UUID, action: str | None = None
) -> list[MergeCandidate]:
    """List candidates for a scan, optionally filtered by action."""
    stmt = select(MergeCandidate).where(MergeCandidate.scan_id == scan_id)
    if action:
        stmt = stmt.where(MergeCandidate.action == action)
    stmt = stmt.order_by(MergeCandidate.overall_score.desc())
    return list(db.scalars(stmt))


def resolve_candidate(
    db: Session,
    candidate_id: uuid.UUID,
    action: str,
    kept_id: uuid.UUID | None = None,
    analyst_note: str | None = None,
) -> MergeCandidate:
    """Apply the analyst's decision to a merge candidate.

    Parameters
    ----------
    candidate_id : uuid.UUID
    action : str
        One of: ``merge``, ``keep_separate``, ``mark_duplicate``.
    kept_id : uuid.UUID | None
        Required when action is ``merge`` — which finding survives.
    analyst_note : str | None
        Free-text reasoning from the analyst.

    Returns
    -------
    MergeCandidate
        The updated candidate.

    Raises
    ------
    ValueError
        If action is invalid, or kept_id is required but missing, or
        kept_id is not one of the two findings in the candidate.
    """
    candidate = db.get(MergeCandidate, candidate_id)
    if candidate is None:
        raise ValueError(f"Candidate {candidate_id} not found")

    action = MergeCandidate.validate_action(action)

    if action == "merge":
        if kept_id is None:
            raise ValueError("kept_id is required when action is 'merge'")
        if kept_id not in (candidate.finding_a_id, candidate.finding_b_id):
            raise ValueError(
                f"kept_id {kept_id} is not one of the candidate's findings "
                f"({candidate.finding_a_id}, {candidate.finding_b_id})"
            )

        # The "loser" finding gets closed. We set its status to
        # "accepted-risk" with a note that it's a duplicate — this
        # preserves the record while stopping double-counting.
        loser_id = (
            candidate.finding_b_id if kept_id == candidate.finding_a_id
            else candidate.finding_a_id
        )
        loser = db.get(Finding, loser_id)
        if loser is not None:
            # Only close it if it's still open — don't overwrite a
            # finding the analyst has already actioned.
            if loser.status.value == "open":
                loser.status = FindingStatus.ACCEPTED_RISK
            # Add a merge note to the finding's notes.
            note_prefix = f"[MERGED into {kept_id}]"
            if analyst_note:
                note_prefix += f" {analyst_note}"
            loser.notes = (loser.notes or "") + f"\n{note_prefix}"

        candidate.kept_id = kept_id

    elif action == "mark_duplicate":
        # Close both findings as accepted-risk.
        for fid in (candidate.finding_a_id, candidate.finding_b_id):
            f = db.get(Finding, fid)
            if f is None:
                continue
            if f.status.value == "open":
                f.status = FindingStatus.ACCEPTED_RISK
            note = f"[MARKED DUPLICATE with {fid}]"
            if analyst_note:
                note += f" {analyst_note}"
            f.notes = (f.notes or "") + f"\n{note}"

    # keep_separate: nothing to do to the findings, just record the decision.

    candidate.action = action
    candidate.analyst_note = analyst_note
    candidate.resolved_at = func.now()

    db.commit()
    return candidate
