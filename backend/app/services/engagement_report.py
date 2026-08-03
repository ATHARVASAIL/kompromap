"""Full-engagement reporting.

The existing reporting module narrates a *single* chain. This one assembles
the whole engagement into the document a tester actually hands over:
executive summary, scope inventory, every finding grouped by severity,
every attack chain with its scoring rationale, and prioritised
remediation.

Design notes worth knowing:

* **Severity bands are derived from CVSS**, not stored. The data model has
  no severity enum (only `cvss_score`), so bands come from CVSS v3's
  standard cutoffs here — the same cutoffs the frontend uses in
  `styles/tokens.ts`. Both must agree or the report contradicts the UI.

* **Remediation priority is chain-aware, not severity-aware.** A medium
  finding sitting on the cheapest path to a crown jewel matters more than
  an unreachable critical. Ranking purely by CVSS would reproduce exactly
  the flat table this tool exists to replace.

* **Nothing is invented.** Where evidence, CVSS or a vector is missing,
  the report says so rather than filling the gap — a report that quietly
  implies more rigour than was performed is worse than an incomplete one.
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    Asset,
    DataStore,
    Edge,
    Endpoint,
    Engagement,
    Finding,
    Node,
    NodeType,
    Service,
    WebApplication,
)
from app.services.pathfinding import find_best_paths_report
from app.services.scoring import DEFAULT_WEIGHTS, ScoringWeights, edge_cost, score_finding

# CVSS v3 bands — must match severityFromCvss() in frontend/src/styles/tokens.ts.
SEVERITY_BANDS: list[tuple[str, float]] = [
    ("Critical", 9.0),
    ("High", 7.0),
    ("Medium", 4.0),
    ("Low", 0.1),
]
SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Informational"]


def severity_for(cvss: float | None) -> str:
    if cvss is None:
        return "Informational"
    for label, floor in SEVERITY_BANDS:
        if cvss >= floor:
            return label
    return "Informational"


@dataclass
class FindingEntry:
    id: uuid.UUID
    title: str
    severity: str
    cvss_score: float | None
    cvss_vector: str | None
    cwe: str | None
    owasp_category: str | None
    status: str
    evidence: str | None
    exploit_public: bool
    auth_required: bool
    affected: list[str] = field(default_factory=list)
    ease_score: float | None = None
    complexity_measured: bool = False
    in_chain: bool = False


@dataclass
class ChainEntry:
    rank: int
    entry_point: str
    crown_jewel: str
    total_cost: float
    exploit_step_count: int
    steps: list[dict]
    narrative: str | None = None


@dataclass
class EngagementReport:
    engagement_name: str
    client_name: str | None
    generated_at: datetime
    summary: dict
    scope: dict
    findings: list[FindingEntry]
    chains: list[ChainEntry]
    remediation: list[dict]
    caveats: list[str]


def _node_label(node: Node) -> str:
    if isinstance(node, Asset):
        return node.name
    if isinstance(node, Service):
        return f"{node.protocol}/{node.port}"
    if isinstance(node, WebApplication):
        return node.name
    if isinstance(node, Endpoint):
        return node.path
    if isinstance(node, DataStore):
        return node.name
    if isinstance(node, Finding):
        return node.title
    return getattr(node, "username", None) or getattr(node, "cred_type", None) or str(node.id)[:8]


def _affected_labels(finding: Finding, edges: list[Edge], by_id: dict) -> list[str]:
    """What this finding was found on — the inverse of HAS_FINDING."""
    labels = []
    for e in edges:
        if e.target_node_id == finding.id and e.edge_type == "HAS_FINDING":
            host = by_id.get(e.source_node_id)
            if host is not None:
                labels.append(_node_label(host))
    return labels


def build_engagement_report(
    db: Session,
    engagement: Engagement,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    include_narratives: bool = False,
) -> EngagementReport:
    nodes: list[Node] = (
        db.query(Node).filter(Node.engagement_id == engagement.id).all()
    )
    node_ids = {n.id for n in nodes}
    edges: list[Edge] = [
        e
        for e in db.query(Edge).all()
        if e.source_node_id in node_ids and e.target_node_id in node_ids
    ]
    by_id = {n.id: n for n in nodes}

    findings = [n for n in nodes if isinstance(n, Finding)]
    entry_points = [n for n in nodes if n.is_entry_point]
    crown_jewels = [n for n in nodes if n.is_crown_jewel]

    # --- Attack chains -------------------------------------------------
    chains: list[ChainEntry] = []
    chain_finding_ids: set[uuid.UUID] = set()

    if entry_points and crown_jewels:
        report = find_best_paths_report(nodes, edges, entry_points, crown_jewels, weights)
        for rank, path in enumerate(report.paths, start=1):
            steps = []
            for i, edge in enumerate(path.edges):
                source = by_id.get(edge.source_node_id)
                target = by_id.get(edge.target_node_id)
                cost = edge_cost(edge, source, weights) if source else 0.0
                if isinstance(source, Finding):
                    chain_finding_ids.add(source.id)
                steps.append(
                    {
                        "index": i + 1,
                        "from": _node_label(source) if source else "?",
                        "to": _node_label(target) if target else "?",
                        "relationship": edge.edge_type,
                        "cost": round(cost, 4),
                        "is_exploit": cost > 0 or edge.edge_type == "YIELDS",
                    }
                )
            chains.append(
                ChainEntry(
                    rank=rank,
                    entry_point=_node_label(path.entry_point),
                    crown_jewel=_node_label(path.crown_jewel),
                    total_cost=round(path.total_cost, 4),
                    exploit_step_count=sum(1 for s in steps if s["is_exploit"]),
                    steps=steps,
                )
            )

    if include_narratives and chains:
        from app.services.reporting import generate_narrative, resolve_chain

        for chain, path in zip(chains, report.paths):
            try:
                text, _ = generate_narrative(resolve_chain(db, [n.id for n in path.nodes]))
                chain.narrative = text
            except Exception:
                # A narrative is a nicety; never let it sink the report.
                chain.narrative = None

    # --- Findings ------------------------------------------------------
    entries: list[FindingEntry] = []
    for f in findings:
        breakdown = score_finding(f, weights)
        entries.append(
            FindingEntry(
                id=f.id,
                title=f.title,
                severity=severity_for(f.cvss_score),
                cvss_score=f.cvss_score,
                cvss_vector=f.cvss_vector,
                cwe=f.cwe,
                owasp_category=f.owasp_category,
                status=f.status,
                evidence=f.evidence,
                exploit_public=f.exploit_public,
                auth_required=f.auth_required,
                affected=_affected_labels(f, edges, by_id),
                ease_score=round(breakdown.ease_score, 4),
                complexity_measured=breakdown.complexity_is_measured,
                in_chain=f.id in chain_finding_ids,
            )
        )
    entries.sort(key=lambda e: (SEVERITY_ORDER.index(e.severity), -(e.cvss_score or 0)))

    severity_counts = Counter(e.severity for e in entries)

    # --- Scope ---------------------------------------------------------
    by_type: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        by_type[n.node_type].append(_node_label(n))

    scope = {
        "assets": sorted(by_type.get(NodeType.ASSET.value, [])),
        "services": sorted(by_type.get(NodeType.SERVICE.value, [])),
        "web_applications": sorted(by_type.get(NodeType.WEB_APPLICATION.value, [])),
        "endpoints": sorted(by_type.get(NodeType.ENDPOINT.value, [])),
        "data_stores": sorted(by_type.get(NodeType.DATA_STORE.value, [])),
        "entry_points": sorted(_node_label(n) for n in entry_points),
        "crown_jewels": sorted(_node_label(n) for n in crown_jewels),
        "node_counts": {k: len(v) for k, v in sorted(by_type.items())},
        "edge_counts": dict(Counter(e.edge_type for e in edges)),
    }

    # --- Remediation, ranked by chain impact ---------------------------
    remediation = _build_remediation(entries, chains)

    # --- Caveats — say what the report does NOT know -------------------
    caveats = _build_caveats(entries, entry_points, crown_jewels, chains)

    summary = {
        "total_findings": len(entries),
        "severity_counts": {s: severity_counts.get(s, 0) for s in SEVERITY_ORDER},
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "entry_point_count": len(entry_points),
        "crown_jewel_count": len(crown_jewels),
        "chain_count": len(chains),
        "easiest_chain_cost": chains[0].total_cost if chains else None,
        "findings_on_a_chain": sum(1 for e in entries if e.in_chain),
        "findings_with_measured_complexity": sum(1 for e in entries if e.complexity_measured),
    }

    return EngagementReport(
        engagement_name=engagement.name,
        client_name=engagement.client_name,
        generated_at=datetime.now(timezone.utc),
        summary=summary,
        scope=scope,
        findings=entries,
        chains=chains,
        remediation=remediation,
        caveats=caveats,
    )


def _build_remediation(entries: list[FindingEntry], chains: list[ChainEntry]) -> list[dict]:
    """Rank fixes by chain impact rather than raw severity.

    Breaking any single step breaks the whole chain, so a finding on the
    cheapest path is worth more than a higher-CVSS finding nothing depends
    on. That inversion is the point of the tool; the report would
    undermine it by falling back to a CVSS sort.
    """
    items = []
    for e in entries:
        if e.status != "open":
            continue
        priority = 0.0
        rationale = []

        if e.in_chain:
            # Position matters: earlier chains are cheaper for an attacker.
            best_rank = min(
                (c.rank for c in chains if any(s["from"] == e.title for s in c.steps)),
                default=len(chains) + 1,
            )
            priority += 100 / best_rank
            rationale.append(f"on attack chain #{best_rank}")

        priority += (e.cvss_score or 0) * 2
        if e.exploit_public:
            priority += 10
            rationale.append("public exploit available")
        if not e.auth_required:
            priority += 8
            rationale.append("exploitable without credentials")
        if not rationale:
            rationale.append("severity-based ranking only — not on any known chain")

        items.append(
            {
                "title": e.title,
                "severity": e.severity,
                "cvss_score": e.cvss_score,
                "affected": e.affected,
                "priority_score": round(priority, 2),
                "rationale": rationale,
                "breaks_chain": e.in_chain,
            }
        )

    items.sort(key=lambda i: -i["priority_score"])
    for i, item in enumerate(items, start=1):
        item["rank"] = i
    return items


def _build_caveats(
    entries: list[FindingEntry],
    entry_points: list[Node],
    crown_jewels: list[Node],
    chains: list[ChainEntry],
) -> list[str]:
    """State the report's own limitations. A deliverable that implies more
    rigour than was performed is worse than one with visible gaps."""
    caveats: list[str] = []

    if not entry_points:
        caveats.append(
            "No entry points were tagged, so no attack chains could be computed. "
            "Chain analysis requires at least one entry point and one crown jewel."
        )
    if not crown_jewels:
        caveats.append(
            "No crown jewels were tagged, so there was no target to measure paths against."
        )
    if entry_points and crown_jewels and not chains:
        caveats.append(
            "Entry points and crown jewels were tagged, but no chain connects them. "
            "This usually means exploitation edges (YIELDS, AUTHENTICATES_AS, "
            "GRANTS_ACCESS_TO) have not been added yet — it is not evidence that no path exists."
        )

    assumed = [e for e in entries if not e.complexity_measured]
    if assumed:
        caveats.append(
            f"{len(assumed)} of {len(entries)} findings have no CVSS vector, so their attack "
            "complexity is an assumed default rather than a measured value. Their ease scores "
            "carry correspondingly less confidence."
        )

    no_evidence = [e for e in entries if not e.evidence]
    if no_evidence:
        caveats.append(
            f"{len(no_evidence)} findings have no recorded evidence. Reproduction steps should "
            "be added before this report is relied upon."
        )

    no_cvss = [e for e in entries if e.cvss_score is None]
    if no_cvss:
        caveats.append(
            f"{len(no_cvss)} findings have no CVSS score and are ranked as Informational by "
            "default; they may warrant manual triage."
        )

    off_chain = [e for e in entries if not e.in_chain and e.severity in ("Critical", "High")]
    if off_chain:
        caveats.append(
            f"{len(off_chain)} Critical/High findings do not appear on any computed chain. "
            "They may still be exploitable in ways not yet modelled in the graph."
        )

    return caveats
