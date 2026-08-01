"""Engagement (workspace) endpoints — spec §5 Phase 4 / §7 Phase 6:
"Multiple engagements/workspaces, each with its own isolated graph."
"""
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Edge, Engagement, Node
from app.schemas.dashboard import DashboardResponse
from app.schemas.engagement import EngagementCreate, EngagementRead, EngagementUpdate
from app.services.engagements import get_active_engagement, set_active_engagement
from app.services.pathfinding import find_best_paths_report
from app.services.scoring import DEFAULT_WEIGHTS

router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.post("", response_model=EngagementRead, status_code=201)
def create_engagement(payload: EngagementCreate, db: Session = Depends(get_db)):
    engagement = Engagement(name=payload.name, client_name=payload.client_name, is_active=False)
    db.add(engagement)
    db.commit()
    db.refresh(engagement)

    if payload.activate:
        engagement = set_active_engagement(db, engagement.id)

    return EngagementRead.model_validate(engagement)


@router.get("", response_model=list[EngagementRead])
def list_engagements(db: Session = Depends(get_db)):
    # Make sure the active-engagement invariant is established (auto-creates
    # a default on a totally fresh DB) so a brand-new install's switcher
    # isn't empty.
    get_active_engagement(db)
    engagements = db.scalars(select(Engagement).order_by(Engagement.created_at))
    return [EngagementRead.model_validate(e) for e in engagements]


@router.get("/active", response_model=EngagementRead)
def get_active(db: Session = Depends(get_db)):
    return EngagementRead.model_validate(get_active_engagement(db))


@router.get("/{engagement_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(engagement_id: uuid.UUID, db: Session = Depends(get_db)):
    """Spec §5 Phase 4 / §7 Phase 6: "Dashboard: node/edge counts, number of
    paths to crown jewels, highest-ease chain found."""
    from app.api.pathfind import _to_path_result  # local import avoids a circular import at module load

    if db.get(Engagement, engagement_id) is None:
        raise HTTPException(404, "Engagement not found")

    nodes = list(db.scalars(select(Node).where(Node.engagement_id == engagement_id)))
    node_ids = {n.id for n in nodes}
    edges = [
        e for e in db.scalars(select(Edge)) if e.source_node_id in node_ids and e.target_node_id in node_ids
    ]

    entry_points = [n for n in nodes if n.is_entry_point]
    crown_jewels = [n for n in nodes if n.is_crown_jewel]

    paths_count = 0
    highest_ease_chain = None
    if entry_points and crown_jewels:
        report = find_best_paths_report(nodes, edges, entry_points, crown_jewels, DEFAULT_WEIGHTS)
        paths_count = len(report.paths)
        if report.paths:
            highest_ease_chain = _to_path_result(report.paths[0])  # already sorted cheapest-first

    return DashboardResponse(
        total_nodes=len(nodes),
        total_edges=len(edges),
        node_counts_by_type=dict(Counter(n.node_type for n in nodes)),
        edge_counts_by_type=dict(Counter(e.edge_type for e in edges)),
        entry_point_count=len(entry_points),
        crown_jewel_count=len(crown_jewels),
        paths_to_crown_jewels_count=paths_count,
        highest_ease_chain=highest_ease_chain,
    )


@router.get("/{engagement_id}", response_model=EngagementRead)
def get_engagement(engagement_id: uuid.UUID, db: Session = Depends(get_db)):
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, "Engagement not found")
    return EngagementRead.model_validate(engagement)


@router.patch("/{engagement_id}", response_model=EngagementRead)
def update_engagement(engagement_id: uuid.UUID, payload: EngagementUpdate, db: Session = Depends(get_db)):
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, "Engagement not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(engagement, field, value)

    db.commit()
    db.refresh(engagement)
    return EngagementRead.model_validate(engagement)


@router.post("/{engagement_id}/activate", response_model=EngagementRead)
def activate_engagement(engagement_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        engagement = set_active_engagement(db, engagement_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return EngagementRead.model_validate(engagement)


@router.delete("/{engagement_id}", status_code=204)
def delete_engagement(engagement_id: uuid.UUID, db: Session = Depends(get_db)):
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, "Engagement not found")

    has_nodes = db.scalar(select(Node).where(Node.engagement_id == engagement_id).limit(1))
    if has_nodes is not None:
        raise HTTPException(
            409,
            "Engagement still has nodes — delete or reassign them first. "
            "Deleting a populated engagement is blocked to prevent accidental data loss.",
        )

    db.delete(engagement)
    db.commit()
