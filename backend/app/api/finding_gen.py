"""AI finding generator endpoints (Phase 4)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Node, NodeType
from app.schemas.finding_gen import FindingGenerateRequest, FindingGenerateResponse, GeneratedFindingRead
from app.services.ai.finding_gen import generate_findings

router = APIRouter(prefix="/finding-gen", tags=["finding-gen"])


def _node_to_properties(node: Node) -> tuple[str, dict]:
    """Convert a node to (node_type_label, properties_dict) for the AI."""
    ntype = node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type)
    props: dict = {}
    for attr in (
        "name", "title", "path", "asset_type",
        "ip_address", "hostname", "port", "service_name",
        "technology", "data_classification", "os", "version",
        "url", "method", "parameter", "evidence", "notes",
    ):
        val = getattr(node, attr, None)
        if val:
            props[attr] = str(val)
    return ntype, props


@router.post("/generate", response_model=FindingGenerateResponse)
def generate_finding_suggestions(
    payload: FindingGenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate AI-suggested findings for a node.

    Results are advisory only. Nothing is written to the database.
    The analyst reviews, edits, and submits via the manual-finding form.
    """
    node = db.get(Node, payload.node_id)
    if node is None:
        raise HTTPException(404, "Node not found")

    if node.node_type == NodeType.FINDING.value:
        raise HTTPException(
            422,
            "Cannot generate findings for an existing finding. Select an asset or endpoint.",
        )

    node_type, properties = _node_to_properties(node)
    outcome = generate_findings(
        node_type=node_type,
        properties=properties,
        target_assets=payload.target_assets or None,
    )

    if not outcome.ok and outcome.error:
        raise HTTPException(502, outcome.error)

    # Collect top-level assumptions from all findings
    all_assumptions: list[str] = []
    for f in (outcome.findings or []):
        all_assumptions.extend(getattr(f, "assumptions", []))

    return FindingGenerateResponse(
        findings=[GeneratedFindingRead(**f.model_dump(mode="json")) for f in (outcome.findings or [])],
        model=outcome.model,
        generated_at=outcome.generated_at,
        assumptions=all_assumptions[:10],
    )


@router.get("/health")
def finding_gen_health():
    """Check whether the AI provider is configured."""
    from app.services.ai.provider import get_provider
    p = get_provider()
    return {"configured": p.is_configured, "provider": type(p).__name__}
