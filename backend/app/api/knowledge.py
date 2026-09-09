"""Knowledge base API endpoints (Phase 5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.db import get_db
from app.models.knowledge_base import KnowledgeBaseEntry
from app.schemas.dashboard import RiskFactorResponse
from app.services.knowledge_base import search_kb, get_kb_entry, create_kb_entry, find_similar
from app.services.engagements import resolve_engagement_id

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("")
def list_kb(query: str | None = None, db: Session = Depends(get_db)):
    entries = search_kb(db, query)
    return [
        {
            "id": str(e.id),
            "reference_id": e.reference_id,
            "title": e.title,
            "description": e.description,
            "source": e.source,
            "severity": e.severity,
            "tags": e.tags,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        }
        for e in entries
    ]


@router.get("/{entry_id}")
def get_kb(entry_id: str, db: Session = Depends(get_db)):
    try:
        eid = UUID(entry_id)
    except ValueError:
        raise HTTPException(422, "Invalid entry ID")
    entry = get_kb_entry(db, eid)
    if not entry:
        raise HTTPException(404, "Knowledge base entry not found")
    return {
        "id": str(entry.id),
        "reference_id": entry.reference_id,
        "title": entry.title,
        "description": entry.description,
        "source": entry.source,
        "severity": entry.severity,
        "tags": entry.tags,
        "mitigations": entry.mitigations,
        "references": entry.references,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


@router.post("/search/similar")
def search_similar(title: str, cwe: str | None = None, limit: int = 5, db: Session = Depends(get_db)):
    return find_similar(db, title, cwe, limit)
