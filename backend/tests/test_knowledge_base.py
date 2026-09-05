"""Knowledge base tests — CRUD, seed data, similarity search."""
import uuid

import pytest

from app.models import KnowledgeBaseEntry
from app.services.knowledge_base import (
    SEED_ENTRIES,
    SimilarEntry,
    create_entry,
    delete_entry,
    get_entry,
    list_entries,
    seed_knowledge_base,
    similarity_search,
    update_entry,
)


def _entry(db, **kw):
    e = KnowledgeBaseEntry(
        id=uuid.uuid4(),
        name=kw.pop("name", "Test"),
        description=kw.pop("description", "A test entry"),
        **kw,
    )
    db.add(e)
    db.flush()
    return e


class TestCRUD:
    def test_create_entry(self, db_session):
        entry = create_entry(
            db_session,
            cwe_id="CWE-79",
            name="XSS",
            description="Cross-site scripting",
            tags=["xss", "web"],
        )
        assert entry.id is not None
        assert entry.cwe_id == "CWE-79"

    def test_get_entry(self, db_session):
        created = _entry(db_session)
        found = get_entry(db_session, created.id)
        assert found is not None
        assert found.name == "Test"

    def test_get_missing_returns_none(self, db_session):
        assert get_entry(db_session, uuid.uuid4()) is None

    def test_list_entries(self, db_session):
        _entry(db_session, cwe_id="CWE-79")
        _entry(db_session, cwe_id="CWE-89")
        entries = list_entries(db_session)
        assert len(entries) == 2

    def test_list_filter_by_cwe(self, db_session):
        _entry(db_session, cwe_id="CWE-79")
        _entry(db_session, cwe_id="CWE-89")
        entries = list_entries(db_session, cwe_id="CWE-79")
        assert len(entries) == 1
        assert entries[0].cwe_id == "CWE-79"

    def test_list_filter_by_tag(self, db_session):
        _entry(db_session, tags=["xss", "web"])
        _entry(db_session, tags=["sqli", "database"])
        entries = list_entries(db_session, tag="xss")
        assert len(entries) == 1

    def test_list_search_name(self, db_session):
        _entry(db_session, name="SQL Injection")
        _entry(db_session, name="XSS")
        entries = list_entries(db_session, search="SQL")
        assert len(entries) == 1

    def test_update_entry(self, db_session):
        created = _entry(db_session)
        updated = update_entry(db_session, created.id, name="Updated Name")
        assert updated is not None
        assert updated.name == "Updated Name"

    def test_update_missing_returns_none(self, db_session):
        assert update_entry(db_session, uuid.uuid4(), name="X") is None

    def test_delete_entry(self, db_session):
        created = _entry(db_session)
        assert delete_entry(db_session, created.id) is True
        assert get_entry(db_session, created.id) is None

    def test_delete_missing_returns_false(self, db_session):
        assert delete_entry(db_session, uuid.uuid4()) is False


class TestSeed:
    def test_seed_inserts_entries(self, db_session):
        n = seed_knowledge_base(db_session)
        assert n == len(SEED_ENTRIES)

    def test_seed_idempotent(self, db_session):
        seed_knowledge_base(db_session)
        n = seed_knowledge_base(db_session)
        assert n == 0

    def test_seed_has_expected_entries(self, db_session):
        seed_knowledge_base(db_session)
        entries = list_entries(db_session, limit=20)
        cwes = {e.cwe_id for e in entries}
        assert "CWE-79" in cwes
        assert "CWE-89" in cwes
        assert "CWE-78" in cwes


class TestSimilaritySearch:
    def test_exact_cwe_match_scores_highest(self, db_session):
        seed_knowledge_base(db_session)
        result = similarity_search(
            db_session, cwe_id="CWE-79", tags=["xss"], description="cross-site scripting"
        )
        assert len(result.matches) > 0
        assert result.matches[0].cwe_id == "CWE-79"
        assert result.matches[0].score > 0.5

    def test_tag_overlap_scores(self, db_session):
        seed_knowledge_base(db_session)
        result = similarity_search(
            db_session, tags=["injection", "database"]
        )
        # Should find SQL injection (has injection + database tags)
        sqli = [m for m in result.matches if m.cwe_id == "CWE-89"]
        assert len(sqli) == 1
        assert sqli[0].score > 0.3

    def test_keyword_overlap(self, db_session):
        seed_knowledge_base(db_session)
        result = similarity_search(
            db_session, description="server-side request forgery SSRF"
        )
        assert len(result.matches) > 0
        ssrf = [m for m in result.matches if m.cwe_id == "CWE-918"]
        assert len(ssrf) == 1

    def test_min_score_filters_low_results(self, db_session):
        seed_knowledge_base(db_session)
        result = similarity_search(
            db_session, description="completely unrelated keyword xyzzy", min_score=0.5
        )
        # No high-scoring match for nonsense keywords
        assert len(result.matches) == 0

    def test_top_n_limits_results(self, db_session):
        seed_knowledge_base(db_session)
        result = similarity_search(
            db_session, tags=["web"], top_n=2
        )
        assert len(result.matches) <= 2

    def test_no_query_returns_empty(self, db_session):
        seed_knowledge_base(db_session)
        result = similarity_search(db_session)
        assert len(result.matches) == 0

    def test_empty_db_returns_empty(self, db_session):
        result = similarity_search(db_session, cwe_id="CWE-79")
        assert len(result.matches) == 0
