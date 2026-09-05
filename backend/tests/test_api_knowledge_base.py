"""API tests for knowledge base endpoints."""
import uuid

import pytest

from app.models import KnowledgeBaseEntry
from app.services.knowledge_base import seed_knowledge_base


def _kb_entry(db, **kw):
    e = KnowledgeBaseEntry(
        id=uuid.uuid4(),
        name="XSS",
        description="Cross-site scripting",
        **kw,
    )
    db.add(e)
    db.flush()
    return e


class TestKbList:
    def test_empty_list(self, client):
        resp = client.get("/api/knowledge-base/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_entries(self, client, db_session):
        _kb_entry(db_session, cwe_id="CWE-79")
        _kb_entry(db_session, cwe_id="CWE-89")
        resp = client.get("/api/knowledge-base/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_cwe(self, client, db_session):
        _kb_entry(db_session, cwe_id="CWE-79")
        _kb_entry(db_session, cwe_id="CWE-89")
        resp = client.get("/api/knowledge-base/?cwe_id=CWE-79")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["cwe_id"] == "CWE-79"

    def test_filter_by_tag(self, client, db_session):
        _kb_entry(db_session, tags=["xss"])
        _kb_entry(db_session, tags=["sqli"])
        resp = client.get("/api/knowledge-base/?tag=xss")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_search_name(self, client, db_session):
        _kb_entry(db_session, name="SQL Injection")
        _kb_entry(db_session, name="XSS")
        resp = client.get("/api/knowledge-base/?search=SQL")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestKbCRUD:
    def test_create_entry(self, client):
        resp = client.post(
            "/api/knowledge-base/",
            json={"cwe_id": "CWE-79", "name": "XSS", "description": "test"},
        )
        assert resp.status_code == 201
        assert resp.json()["cwe_id"] == "CWE-79"

    def test_get_entry(self, client, db_session):
        entry = _kb_entry(db_session, cwe_id="CWE-79")
        db_session.commit()
        resp = client.get(f"/api/knowledge-base/{entry.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "XSS"

    def test_get_not_found(self, client):
        resp = client.get(f"/api/knowledge-base/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_entry(self, client, db_session):
        entry = _kb_entry(db_session)
        db_session.commit()
        resp = client.put(
            f"/api/knowledge-base/{entry.id}",
            json={"name": "Updated XSS"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated XSS"

    def test_delete_entry(self, client, db_session):
        entry = _kb_entry(db_session)
        db_session.commit()
        resp = client.delete(f"/api/knowledge-base/{entry.id}")
        assert resp.status_code == 204
        assert client.get(f"/api/knowledge-base/{entry.id}").status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete(f"/api/knowledge-base/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestKbSeed:
    def test_seed_endpoint(self, client, db_session):
        seed_knowledge_base(db_session)
        resp = client.post("/api/knowledge-base/seed")
        assert resp.status_code == 201
        data = resp.json()
        assert "inserted" in data
        assert data["inserted"] == 0  # already seeded


class TestKbSimilarity:
    def test_search_requires_at_least_one_query(self, client):
        resp = client.post("/api/knowledge-base/search", json={})
        assert resp.status_code == 422

    def test_similarity_search(self, client, db_session):
        seed_knowledge_base(db_session)
        resp = client.post(
            "/api/knowledge-base/search",
            json={"cwe_id": "CWE-79", "tags": ["xss"], "top_n": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["matches"]) > 0
        assert data["matches"][0]["cwe_id"] == "CWE-79"

    def test_similarity_search_no_match(self, client, db_session):
        seed_knowledge_base(db_session)
        resp = client.post(
            "/api/knowledge-base/search",
            json={"description": "completely unrelated nonsense xyzzy", "min_score": 0.5},
        )
        assert resp.status_code == 200
        assert len(resp.json()["matches"]) == 0
