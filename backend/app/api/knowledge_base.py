"""Knowledge base API endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.knowledge_base import (
    KnowledgeBaseEntryCreate,
    KnowledgeBaseEntryResponse,
    KnowledgeBaseEntryUpdate,
    SimilarSearchRequest,
    SimilarSearchResponse,
)
from app.services.knowledge_base import (
    create_entry,
    delete_entry,
    get_entry,
    list_entries,
    seed_knowledge_base,
    similarity_search,
    update_entry,
)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("/", response_model=list[KnowledgeBaseEntryResponse])
def list_kb_entries(
    cwe_id: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_entries(db, cwe_id=cwe_id, tag=tag, search=search, limit=limit)


@router.get("/{entry_id}", response_model=KnowledgeBaseEntryResponse)
def get_kb_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = get_entry(db, entry_id)
    if entry is None:
        raise HTTPException(404, "Knowledge base entry not found")
    return entry


@router.post("/", response_model=KnowledgeBaseEntryResponse, status_code=201)
def create_kb_entry(payload: KnowledgeBaseEntryCreate, db: Session = Depends(get_db)):
    return create_entry(db, **payload.model_dump())


@router.put("/{entry_id}", response_model=KnowledgeBaseEntryResponse)
def update_kb_entry(
    entry_id: uuid.UUID, payload: KnowledgeBaseEntryUpdate, db: Session = Depends(get_db)
):
    entry = update_entry(db, entry_id, **payload.model_dump(exclude_none=True))
    if entry is None:
        raise HTTPException(404, "Knowledge base entry not found")
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_kb_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = delete_entry(db, entry_id)
    if not ok:
        raise HTTPException(404, "Knowledge base entry not found")


@router.post("/search", response_model=SimilarSearchResponse)
def search_similar(payload: SimilarSearchRequest, db: Session = Depends(get_db)):
    result = similarity_search(
        db,
        cwe_id=payload.cwe_id,
        tags=payload.tags,
        description=payload.description,
        top_n=payload.top_n,
        min_score=payload.min_score,
    )
    return SimilarSearchResponse(
        query_cwe=result.query_cwe,
        query_tags=result.query_tags,
        matches=[
            {
                "entry_id": m.entry_id,
                "cwe_id": m.cwe_id,
                "name": m.name,
                "score": m.score,
                "match_reason": m.match_reason,
            }
            for m in result.matches
        ],
    )


@router.post("/seed", status_code=201)
def seed_endpoint(db: Session = Depends(get_db)):
    """Load default CWE entries into the knowledge base."""
    inserted = seed_knowledge_base(db)
    return {"inserted": inserted}
