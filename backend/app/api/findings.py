"""Manual finding entry (spec §5 MVP: "Manual finding entry form"). Creates
a Finding node and wires the HAS_FINDING edge to whatever the tester says
they found it on, in one call — the UI-facing counterpart to file ingestion.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Asset, Edge, EdgeType, Endpoint, Finding, Node, NodeType
from app.schemas.ingest import ManualFindingCreate
from app.schemas.node import FindingRead
from app.services.engagements import resolve_engagement_id

router = APIRouter(prefix="/findings", tags=["findings"])


@router.post("", response_model=FindingRead, status_code=201)
def create_manual_finding(payload: ManualFindingCreate, db: Session = Depends(get_db)):
    target = db.get(Node, payload.target_node_id)
    if target is None:
        raise HTTPException(422, "target_node_id does not reference an existing node")
    if not isinstance(target, (Asset, Endpoint)):
        # Per spec §4's edge table, HAS_FINDING only goes Asset/Endpoint -> Finding.
        raise HTTPException(
            422,
            f"target_node_id must reference an Asset or Endpoint (got {target.node_type})",
        )

    finding = Finding(
        node_type=NodeType.FINDING.value,
        engagement_id=target.engagement_id or resolve_engagement_id(db, None),
        title=payload.title,
        cwe=payload.cwe,
        owasp_category=payload.owasp_category,
        cvss_score=payload.cvss_score,
        exploit_public=payload.exploit_public,
        auth_required=payload.auth_required,
        evidence=payload.evidence,
        status=payload.status.value,
        notes=payload.notes,
    )
    db.add(finding)
    db.flush()

    db.add(
        Edge(
            source_node_id=target.id,
            target_node_id=finding.id,
            edge_type=EdgeType.HAS_FINDING.value,
        )
    )
    db.commit()
    db.refresh(finding)
    return FindingRead.model_validate(finding)
