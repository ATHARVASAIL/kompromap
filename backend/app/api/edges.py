import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Edge, EdgeType, Node
from app.schemas.edge import EdgeCreate, EdgeRead, EdgeUpdate

router = APIRouter(prefix="/edges", tags=["edges"])


@router.post("", response_model=EdgeRead, status_code=201)
def create_edge(payload: EdgeCreate, db: Session = Depends(get_db)):
    if db.get(Node, payload.source_node_id) is None:
        raise HTTPException(422, "source_node_id does not reference an existing node")
    if db.get(Node, payload.target_node_id) is None:
        raise HTTPException(422, "target_node_id does not reference an existing node")

    edge = Edge(
        source_node_id=payload.source_node_id,
        target_node_id=payload.target_node_id,
        edge_type=payload.edge_type.value,
        weight=payload.weight,
        edge_metadata=payload.metadata,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return EdgeRead.from_orm_edge(edge)


@router.get("", response_model=list[EdgeRead])
def list_edges(
    source_node_id: uuid.UUID | None = Query(default=None),
    target_node_id: uuid.UUID | None = Query(default=None),
    edge_type: EdgeType | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(Edge)
    if source_node_id is not None:
        stmt = stmt.where(Edge.source_node_id == source_node_id)
    if target_node_id is not None:
        stmt = stmt.where(Edge.target_node_id == target_node_id)
    if edge_type is not None:
        stmt = stmt.where(Edge.edge_type == edge_type.value)

    edges = db.scalars(stmt)
    return [EdgeRead.from_orm_edge(e) for e in edges]


@router.get("/{edge_id}", response_model=EdgeRead)
def get_edge(edge_id: uuid.UUID, db: Session = Depends(get_db)):
    edge = db.get(Edge, edge_id)
    if edge is None:
        raise HTTPException(404, "Edge not found")
    return EdgeRead.from_orm_edge(edge)


@router.patch("/{edge_id}", response_model=EdgeRead)
def update_edge(edge_id: uuid.UUID, payload: EdgeUpdate, db: Session = Depends(get_db)):
    edge = db.get(Edge, edge_id)
    if edge is None:
        raise HTTPException(404, "Edge not found")

    if payload.edge_type is not None:
        edge.edge_type = payload.edge_type.value
    if payload.weight is not None:
        edge.weight = payload.weight
    if payload.metadata is not None:
        edge.edge_metadata = payload.metadata

    db.commit()
    db.refresh(edge)
    return EdgeRead.from_orm_edge(edge)


@router.delete("/{edge_id}", status_code=204)
def delete_edge(edge_id: uuid.UUID, db: Session = Depends(get_db)):
    edge = db.get(Edge, edge_id)
    if edge is None:
        raise HTTPException(404, "Edge not found")
    db.delete(edge)
    db.commit()
