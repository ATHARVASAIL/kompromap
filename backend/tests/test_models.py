"""Sanity checks on the ORM model layer.

These don't require a live Postgres connection: they compile the models to
Postgres DDL and check the mapper/inheritance configuration directly.
Ingestion/round-trip tests against a real DB belong in Phase 2, once there's
an API layer to exercise.
"""
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.db import Base
from app.models import (
    Account,
    Asset,
    Credential,
    DataStore,
    Edge,
    Endpoint,
    Finding,
    Node,
    NodeType,
    Service,
    WebApplication,
)

NODE_SUBCLASSES = [
    Asset,
    Service,
    WebApplication,
    Endpoint,
    Credential,
    Account,
    DataStore,
    Finding,
]


def test_all_tables_compile_to_postgres_ddl():
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        # Raises if the table can't be compiled for Postgres.
        str(CreateTable(table).compile(dialect=dialect))


def test_expected_tables_exist():
    expected = {
        "nodes",
        "assets",
        "services",
        "web_applications",
        "endpoints",
        "credentials",
        "accounts",
        "data_stores",
        "findings",
        "edges",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_every_node_subclass_has_a_matching_polymorphic_identity():
    for cls in NODE_SUBCLASSES:
        identity = cls.__mapper__.polymorphic_identity
        assert identity == NodeType(identity).value
        assert NodeType(identity) in NodeType


def test_node_base_has_edge_relationships():
    rel_names = set(Node.__mapper__.relationships.keys())
    assert {"outgoing_edges", "incoming_edges"}.issubset(rel_names)


def test_edge_has_source_and_target_foreign_keys_to_nodes():
    targets = {fk.target_fullname for fk in Edge.__table__.foreign_keys}
    assert targets == {"nodes.id", "nodes.id"} or targets == {"nodes.id"}
    assert len(Edge.__table__.foreign_keys) == 2


def test_credential_fk_points_at_findings():
    fk_targets = {fk.target_fullname for fk in Credential.__table__.foreign_keys}
    assert "findings.id" in fk_targets
