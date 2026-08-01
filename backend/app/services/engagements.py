"""Active-engagement resolution — see app/models/engagement.py's docstring
for the design rationale (single active workspace, auto-created default).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Engagement

DEFAULT_ENGAGEMENT_NAME = "Default Engagement"


def get_active_engagement(db: Session) -> Engagement:
    """The engagement that untagged node/edge creation and unscoped
    list/graph/pathfind/reporting calls default to. Auto-creates and
    activates a "Default Engagement" the first time anything needs one."""
    active = db.scalar(select(Engagement).where(Engagement.is_active.is_(True)))
    if active is not None:
        return active

    # No active engagement — either this is a fresh DB, or all engagements
    # somehow got deactivated. Reuse an existing one if present rather than
    # multiplying "Default Engagement" rows.
    existing = db.scalar(select(Engagement).order_by(Engagement.created_at))
    if existing is not None:
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    engagement = Engagement(name=DEFAULT_ENGAGEMENT_NAME, is_active=True)
    db.add(engagement)
    db.commit()
    db.refresh(engagement)
    return engagement


def set_active_engagement(db: Session, engagement_id: uuid.UUID) -> Engagement:
    """Switch the active engagement — the backend for the workspace
    switcher. Returns the newly-active Engagement, or raises ValueError if
    engagement_id doesn't exist."""
    target = db.get(Engagement, engagement_id)
    if target is None:
        raise ValueError(f"Engagement {engagement_id} does not exist")

    db.execute(update(Engagement).where(Engagement.id != engagement_id).values(is_active=False))
    target.is_active = True
    db.commit()
    db.refresh(target)
    return target


def resolve_engagement_id(db: Session, engagement_id: uuid.UUID | None) -> uuid.UUID:
    """Explicit engagement_id wins; otherwise fall back to the active one."""
    if engagement_id is not None:
        return engagement_id
    return get_active_engagement(db).id
