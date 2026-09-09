from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.pathfind import PathResultResponse


class DashboardResponse(BaseModel):
    total_nodes: int
    total_edges: int
    node_counts_by_type: dict[str, int]
    edge_counts_by_type: dict[str, int]
    entry_point_count: int
    crown_jewel_count: int
    paths_to_crown_jewels_count: int
    highest_ease_chain: PathResultResponse | None


class RiskFactorResponse(BaseModel):
    asset_id: str
    name: str
    type: str
    base_cvss: float
    criticality: float
    sensitivity: float
    exposure: float
    extended_risk: float
    finding_count: int
    critical_findings: int
    attack_paths_in: int


class CorrelationResponse(BaseModel):
    engagement_id: str
    total_findings: int
    unique_cwes: int
    cwe_groups: dict[str | None, list[dict[str, Any]]]
    asset_risks: list[RiskFactorResponse]
    assets_exposed: int
    average_risk: float
