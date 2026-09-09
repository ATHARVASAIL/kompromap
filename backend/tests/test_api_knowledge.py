"""API tests for knowledge base endpoints (Phase 5)."""
import uuid


def test_list_kb_empty(client, db_session):
    r = client.get("/api/knowledge")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_get_kb(client, db_session):
    from app.models.knowledge_base import KnowledgeBaseEntry

    entry = KnowledgeBaseEntry(
        source="nvd",
        reference_id=f"CVE-{uuid.uuid4().hex[:8]}",
        title="SQL Injection",
        description="SQL injection vulnerability",
        tags=["CWE-89"],
        severity="high",
    )
    db_session.add(entry)
    db_session.flush()

    r = client.get(f"/api/knowledge/{entry.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "SQL Injection"
    assert body["source"] == "nvd"


def test_get_kb_not_found(client, db_session):
    r = client.get(f"/api/knowledge/{uuid.uuid4()}")
    assert r.status_code == 404


def test_search_kb(client, db_session):
    from app.models.knowledge_base import KnowledgeBaseEntry

    e1 = KnowledgeBaseEntry(
        source="nvd", reference_id="C1", title="XSS vulnerability",
        description="Cross-site scripting", tags=["CWE-79"], severity="medium",
    )
    e2 = KnowledgeBaseEntry(
        source="nvd", reference_id="C2", title="SQL Injection",
        description="SQL injection flaw", tags=["CWE-89"], severity="high",
    )
    db_session.add_all([e1, e2])
    db_session.flush()

    r = client.get("/api/knowledge?query=XSS")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    assert any("XSS" in e["title"] for e in body)


def test_search_similar(client, db_session):
    from app.models.knowledge_base import KnowledgeBaseEntry

    e = KnowledgeBaseEntry(
        source="nvd", reference_id="SIM-1", title="SQL Injection attack",
        description="An attacker can inject SQL", tags=["CWE-89"], severity="high",
    )
    db_session.add(e)
    db_session.flush()

    r = client.get("/api/knowledge/search/similar?title=SQL+Injection&limit=3")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
