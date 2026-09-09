"""Correlation / extended risk model (Phase 3).

Computes an extended risk score beyond CVSS:
  risk = base_cvss * asset_criticality * data_sensitivity * (1 + exposure_bonus)

Asset criticality and data sensitivity come from tags/annotations on
asset nodes. Exposure is derived from edge reachability — how many
entry-point paths lead to this asset.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Asset, DataStore, Edge, EdgeType, Endpoint, Finding, Node


@dataclass
class RiskFactors:
    """Per-asset extended risk breakdown."""
    asset_id: str
    asset_name: str
    asset_type: str
    base_cvss: float
    asset_criticality: float
    data_sensitivity: float
    exposure: float
    extended_risk: float
    finding_count: int
    critical_findings: int
    attack_paths_in: int


def _criticality_score(asset: Asset) -> float:
    """Map asset tags/category to a 0-1 criticality score."""
    criticality_map = {
        "crown-jewel": 1.0,
        "production": 0.8,
        "staging": 0.5,
        "development": 0.3,
        "internal": 0.4,
        "dmz": 0.7,
        "office": 0.2,
        "backup": 0.6,
    }
    tags = asset.tags or []
    for tag in tags:
        if tag.lower() in criticality_map:
            return criticality_map[tag.lower()]
    # Fall back to asset type
    type_scores = {
        "server": 0.7,
        "database": 0.9,
        "workstation": 0.4,
        "network_device": 0.6,
        "iot": 0.5,
        "cloud": 0.6,
    }
    return type_scores.get(asset.asset_type.value.lower(), 0.5)


def _data_sensitivity_score(asset: Asset) -> float:
    """Map data classification tags to a 0-1 sensitivity score."""
    sensitivity_map = {
        "pii": 0.9,
        "phi": 0.95,
        "pci": 0.95,
        "classified": 1.0,
        "confidential": 0.8,
        "internal": 0.4,
        "public": 0.1,
    }
    tags = asset.tags or []
    for tag in tags:
        if tag.lower() in sensitivity_map:
            return sensitivity_map[tag.lower()]
    # Check node-level notes for hints
    notes = (asset.notes or "").lower()
    for keyword, score in sensitivity_map.items():
        if keyword in notes:
            return score
    return 0.5


def _exposure_score(db: Session, asset_id: str) -> tuple[float, int]:
    """Count how many entry-point paths reach this asset.

    Returns (exposure_score, attack_paths_in).
    """
    # An "entry point" is a WebApplication or Service that has an EXPOSES edge
    # from an Asset of type network_device or internet-facing.
    # Simple heuristic: count assets that can reach this one via graph traversal.
    # For now we use a lightweight reachability count.

    # Find all assets that EXPOSE or HOST something that chains to this asset
    stmt = (
        select(Edge.source_node_id)
        .where(and_(Edge.target_node_id == asset_id, Edge.edge_type.in_(["EXPOSES", "HOSTS", "GRANTS_ACCESS_TO"])))
    )
    reachable_from = [row[0] for row in db.execute(stmt).fetchall()]

    # Count how many findings attack paths exist
    path_count = len(reachable_from)

    # Score: 0 if no exposure, up to 1.0 based on reachability
    # 0 paths = 0, 1-3 paths = 0.3, 4-10 = 0.6, 10+ = 0.9
    if path_count == 0:
        return 0.0, 0
    elif path_count <= 3:
        return 0.3, path_count
    elif path_count <= 10:
        return 0.6, path_count
    else:
        return 0.9, path_count


def compute_asset_risk(db: Session, engagement_id: str) -> list[RiskFactors]:
    """Compute extended risk for every asset in the engagement."""
    assets_stmt = (
        select(Asset)
        .join(Node, Asset.id == Node.id)
        .where(and_(Node.engagement_id == engagement_id, Node.node_type == "asset"))
    )
    assets = list(db.execute(assets_stmt).scalars().all())

    results: list[RiskFactors] = []

    for asset in assets:
        criticality = _criticality_score(asset)
        data_sens = _data_sensitivity_score(asset)
        exposure, path_count = _exposure_score(db, asset.id)

        # Base CVSS: max CVSS of findings on this asset
        findings_stmt = (
            select(Finding.cvss_score)
            .join(Edge, Edge.target_node_id == Finding.id)
            .where(and_(Edge.source_node_id == asset.id, Edge.edge_type == EdgeType.HAS_FINDING.value))
        )
        cvss_values = [row[0] for row in db.execute(findings_stmt).fetchall() if row[0] is not None]
        base_cvss = max(cvss_values) if cvss_values else 0.0

        # Count critical findings (CVSS >= 7.0)
        critical_findings = sum(1 for v in cvss_values if v >= 7.0)

        # Count all findings
        finding_count = len(cvss_values)

        # Extended risk formula
        extended = base_cvss * criticality * data_sens * (1.0 + exposure)

        results.append(RiskFactors(
            asset_id=str(asset.id),
            asset_name=asset.name,
            asset_type=asset.asset_type.value,
            base_cvss=round(base_cvss, 2),
            asset_criticality=round(criticality, 2),
            data_sensitivity=round(data_sens, 2),
            exposure=round(exposure, 2),
            extended_risk=round(min(extended, 10.0), 2),  # cap at 10
            finding_count=finding_count,
            critical_findings=critical_findings,
            attack_paths_in=path_count,
        ))

    results.sort(key=lambda r: r.extended_risk, reverse=True)
    return results


def compute_correlation_matrix(db: Session, engagement_id: str) -> dict[str, Any]:
    """Produce data for the correlation view:
    - Finding-finding correlations (same CWE, same asset, same endpoint)
    - Asset risk ranking
    - Data sensitivity hotspots
    """
    # Finding correlations
    findings_stmt = (
        select(Finding.id, Finding.title, Finding.cwe, Finding.cvss_score)
        .join(Node, Finding.id == Node.id)
        .where(and_(Node.engagement_id == engagement_id, Node.node_type == "finding"))
    )
    findings = list(db.execute(findings_stmt).fetchall())

    cwe_groups: dict[str | None, list] = {}
    for fid, title, cwe, cvss in findings:
        cwe_groups.setdefault(cwe, []).append({"id": str(fid), "title": title, "cvss": cvss})

    # Asset risk
    asset_risks = compute_asset_risk(db, engagement_id)

    # Exposure stats
    assets_exposed = sum(1 for r in asset_risks if r.exposure > 0)
    avg_risk = sum(r.extended_risk for r in asset_risks) / max(len(asset_risks), 1)

    return {
        "engagement_id": engagement_id,
        "total_findings": len(findings),
        "unique_cwes": len(cwe_groups),
        "cwe_groups": cwe_groups,
        "asset_risks": [
            {
                "asset_id": r.asset_id,
                "name": r.asset_name,
                "type": r.asset_type,
                "base_cvss": r.base_cvss,
                "criticality": r.asset_criticality,
                "sensitivity": r.data_sensitivity,
                "exposure": r.exposure,
                "extended_risk": r.extended_risk,
                "finding_count": r.finding_count,
                "critical_findings": r.critical_findings,
                "attack_paths_in": r.attack_paths_in,
            }
            for r in asset_risks
        ],
        "assets_exposed": assets_exposed,
        "average_risk": round(avg_risk, 2),
    }
