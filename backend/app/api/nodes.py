"""CRUD for graph nodes.

One generic set of endpoints handles all 8 node types (spec §5 MVP: "manual
finding entry form (create nodes/edges by hand)" — this covers that for
every node type, not just findings; app/api/findings.py adds a
finding-specific convenience endpoint on top since that's the one the spec
calls out by name).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Node, NodeType
from app.models.node import (
    Account,
    Asset,
    Credential,
    DataStore,
    Endpoint,
    Finding,
    Service,
    WebApplication,
)
from app.schemas.node import (
    READ_SCHEMA_BY_TYPE,
    UPDATE_SCHEMA_BY_TYPE,
    NodeCreate,
    NodeRead,
)
from app.services.engagements import resolve_engagement_id

router = APIRouter(prefix="/nodes", tags=["nodes"])

_MODEL_BY_TYPE: dict[NodeType, type[Node]] = {
    NodeType.ASSET: Asset,
    NodeType.SERVICE: Service,
    NodeType.WEB_APPLICATION: WebApplication,
    NodeType.ENDPOINT: Endpoint,
    NodeType.CREDENTIAL: Credential,
    NodeType.ACCOUNT: Account,
    NodeType.DATA_STORE: DataStore,
    NodeType.FINDING: Finding,
}


def _to_read_schema(node: Node) -> NodeRead:
    schema_cls = READ_SCHEMA_BY_TYPE[NodeType(node.node_type)]
    return schema_cls.model_validate(node)


@router.post("", response_model=NodeRead, status_code=201)
def create_node(payload: NodeCreate, db: Session = Depends(get_db)):
    model_cls = _MODEL_BY_TYPE[payload.node_type]
    data = payload.model_dump(exclude={"node_type", "engagement_id"})
    engagement_id = resolve_engagement_id(db, payload.engagement_id)
    node = model_cls(node_type=payload.node_type.value, engagement_id=engagement_id, **data)
    db.add(node)
    db.commit()
    db.refresh(node)
    return _to_read_schema(node)


@router.get("", response_model=list[NodeRead])
def list_nodes(
    node_type: NodeType | None = Query(default=None),
    in_scope: bool | None = Query(default=None, description="Assets only"),
    is_entry_point: bool | None = Query(default=None),
    is_crown_jewel: bool | None = Query(default=None),
    min_cvss: float | None = Query(default=None, description="Findings only"),
    status: str | None = Query(default=None, description="Finding status filter"),
    engagement_id: uuid.UUID | None = Query(default=None, description="Defaults to the active engagement"),
    db: Session = Depends(get_db),
):
    resolved_engagement_id = resolve_engagement_id(db, engagement_id)
    stmt = select(Node).where(Node.engagement_id == resolved_engagement_id)
    if node_type is not None:
        stmt = stmt.where(Node.node_type == node_type.value)
    if is_entry_point is not None:
        stmt = stmt.where(Node.is_entry_point == is_entry_point)
    if is_crown_jewel is not None:
        stmt = stmt.where(Node.is_crown_jewel == is_crown_jewel)

    nodes = list(db.scalars(stmt))

    # Type-specific filters applied in Python rather than pushed into the
    # base query, since they only make sense once we know the subtype.
    if in_scope is not None:
        nodes = [n for n in nodes if not isinstance(n, Asset) or n.in_scope == in_scope]
    if min_cvss is not None:
        nodes = [n for n in nodes if not isinstance(n, Finding) or (n.cvss_score or 0) >= min_cvss]
    if status is not None:
        nodes = [n for n in nodes if not isinstance(n, Finding) or n.status == status]

    return [_to_read_schema(n) for n in nodes]


@router.get("/{node_id}", response_model=NodeRead)
def get_node(node_id: uuid.UUID, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(404, "Node not found")
    return _to_read_schema(node)


@router.patch("/{node_id}", response_model=NodeRead)
def update_node(node_id: uuid.UUID, payload: dict, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(404, "Node not found")

    # The body is typed as a raw dict because the correct update schema
    # depends on the *stored* node's type, which isn't known until after
    # the DB lookup. That means validating by hand here — and Pydantic's
    # ValidationError is NOT the same class FastAPI auto-converts to a 422
    # (that's RequestValidationError, raised only by its own body parsing),
    # so without this catch an invalid field escapes as an unhandled 500.
    update_schema_cls = UPDATE_SCHEMA_BY_TYPE[NodeType(node.node_type)]
    try:
        validated = update_schema_cls.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(422, e.errors()) from e

    for field, value in validated.model_dump(exclude_unset=True).items():
        setattr(node, field, value)

    db.commit()
    db.refresh(node)
    return _to_read_schema(node)


@router.delete("/{node_id}", status_code=204)
def delete_node(node_id: uuid.UUID, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(404, "Node not found")
    db.delete(node)
    db.commit()
