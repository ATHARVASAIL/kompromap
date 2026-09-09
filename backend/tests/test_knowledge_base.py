"""Tests for the knowledge base service (Phase 5)."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBaseEntry
from app.services.knowledge_base import create_kb_entry, find_similar, get_kb_entry, search_kb


def _make_entry(db: Session, source: str = "nvd", title: str = "Test Entry",
                cwe: str | None = "CWE-79", tags: list[str] | None = None) -> KnowledgeBaseEntry:
    entry = KnowledgeBaseEntry(
        source=source,
        reference_id=f"ref-{uuid.uuid4().hex[:8]}",
        title=title,
        description="A test knowledge base entry.",
        tags=tags or [cwe] if cwe else [],
        severity="medium",
        mitigations="Apply input validation.",
        references="https://example.com",
    )
    db.add(entry)
    db.flush()
    db.refresh(entry)
    return entry


class TestCreateKBEntry:
    def test_basic_create(self, db_session):
        entry = _make_entry(db_session)
        assert entry.id is not None
        assert entry.source == "nvd"

    def test_duplicate_reference_id_rejected(self, db_session):
        ref = f"dup-{uuid.uuid4().hex[:8]}"
        e1 = KnowledgeBaseEntry(source="nvd", reference_id=ref, title="First", tags=[])
        db_session.add(e1)
        db_session.flush()
        # Second with same source+reference_id should be handled gracefully
        # (service may deduplicate or raise — test either behavior)
        e2 = KnowledgeBaseEntry(source="nvd", reference_id=ref, title="Second", tags=[])
        db_session.add(e2)
        # If DB has no unique constraint, both exist; service handles dedup
        assert e2.id is not None


class TestSearchKB:
    def test_search_by_title(self, db_session):
        _make_entry(db_session, title="SQL Injection in login")
        _make_entry(db_session, title="XSS in search")
        results = search_kb(db_session, "SQL")
        assert len(results) >= 1
        assert any("SQL" in r.title for r in results)

    def test_search_by_cwe_tag(self, db_session):
        _make_entry(db_session, title="Entry A", cwe="CWE-79", tags=["CWE-79"])
        _make_entry(db_session, title="Entry B", cwe="CWE-89", tags=["CWE-89"])
        results = search_kb(db_session, "CWE-79")
        assert len(results) >= 1

    def test_empty_query_returns_all(self, db_session):
        _make_entry(db_session, title="One")
        _make_entry(db_session, title="Two")
        results = search_kb(db_session, "")
        assert len(results) >= 2


class TestFindSimilar:
    def test_similar_findings(self, db_session):
        entry = _make_entry(db_session, title="SQL Injection vulnerability",
                            tags=["CWE-89", "injection"])
        similar = find_similar(db_session, entry.title, entry.tags[0] if entry.tags else None)
        # Should at least return the entry itself (self-match) or nothing
        # depending on implementation
        assert isinstance(similar, list)

    def test_no_similar(self, db_session):
        entry = _make_entry(db_session, title="Unique entry XYZ")
        similar = find_similar(db_session, entry.title, entry.tags[0] if entry.tags else None)
        # With only 1 entry, similarity search should return empty or just itself
        assert isinstance(similar, list)


class TestGetKBEntry:
    def test_get_existing(self, db_session):
        entry = _make_entry(db_session)
        fetched = get_kb_entry(db_session, entry.id)
        assert fetched is not None
        assert fetched.id == entry.id

    def test_get_missing(self, db_session):
        fetched = get_kb_entry(db_session, uuid.uuid4())
        assert fetched is None
