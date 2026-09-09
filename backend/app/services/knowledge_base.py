"""Knowledge base service (Phase 5).

Maintains a searchable repository of CVE, CWE, mitigation, and
vulnerability pattern data.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBaseEntry


def search_kb(db: Session, query: str | None = None) -> list[KnowledgeBaseEntry]:
    """Search the knowledge base by text query."""
    stmt = select(KnowledgeBaseEntry)
    if query:
        pattern = f"%{query.lower()}%"
        stmt = stmt.where(
            KnowledgeBaseEntry.title.ilike(pattern)
            | KnowledgeBaseEntry.description.ilike(pattern)  # type: ignore[arg-type]
            | KnowledgeBaseEntry.reference_id.ilike(pattern)
        )
    stmt = stmt.order_by(KnowledgeBaseEntry.updated_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_kb_entry(db: Session, entry_id: UUID) -> KnowledgeBaseEntry | None:
    return db.get(KnowledgeBaseEntry, entry_id)


def create_kb_entry(
    db: Session,
    source: str,
    reference_id: str,
    title: str,
    description: str | None = None,
    tags: list[str] | None = None,
    severity: str | None = None,
    mitigations: str | None = None,
    references: str | None = None,
) -> KnowledgeBaseEntry:
    entry = KnowledgeBaseEntry(
        source=source,
        reference_id=reference_id,
        title=title,
        description=description,
        tags=tags or [],
        severity=severity,
        mitigations=mitigations,
        references=references,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def find_similar(db: Session, title: str, cwe: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Find knowledge base entries similar to a finding description.
    Used to suggest mitigations when a new finding is ingested.
    """
    candidates = search_kb(db, cwe or title)
    results = []
    for entry in candidates:
        score = 0.0
        title_words = set(re.findall(r"\b[a-z0-9_]+\b", title.lower()))
        kb_words = set(re.findall(r"\b[a-z0-9_]+\b", (entry.title + " " + (entry.description or "")).lower()))
        if title_words and kb_words:
            score = len(title_words & kb_words) / len(title_words | kb_words)
        if cwe and entry.reference_id.lower() == cwe.lower():
            score += 0.5
        results.append({
            "entry": {
                "id": str(entry.id),
                "reference_id": entry.reference_id,
                "title": entry.title,
                "description": entry.description,
                "severity": entry.severity,
                "mitigations": entry.mitigations,
                "references": entry.references,
            },
            "similarity": round(min(score, 1.0), 3),
        })
    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:limit]
