import uuid

from pydantic import BaseModel

from app.models.enums import FindingStatus


class IngestSummaryResponse(BaseModel):
    source_tool: str
    assets_created: int
    assets_reused: int
    services_created: int
    services_reused: int
    endpoints_created: int
    endpoints_reused: int
    findings_created: int
    edges_created: int
    warnings: list[str]


class ManualFindingCreate(BaseModel):
    """Manual finding-entry form (spec §5 MVP). Attaches directly to a node
    the tester already knows about, rather than resolving from a fuzzy
    string reference the way file ingestion has to."""

    title: str
    target_node_id: uuid.UUID  # must be an Asset or Endpoint (HAS_FINDING per spec §4)
    cwe: str | None = None
    owasp_category: str | None = None
    cvss_score: float | None = None
    exploit_public: bool = False
    auth_required: bool = True
    evidence: str | None = None
    status: FindingStatus = FindingStatus.OPEN
    notes: str | None = None
