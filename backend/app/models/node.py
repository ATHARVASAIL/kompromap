"""Node models — the 8 node types from kompromap-spec.md §4.

Implemented as SQLAlchemy joined-table inheritance: a single `nodes` base
table carries fields common to every node (id, type discriminator,
timestamps, notes, and the entry-point/crown-jewel tags used by
path-finding), and each node type gets its own table for its specific
properties, joined 1:1 on `id`.

Design note — `is_entry_point` / `is_crown_jewel` live on the base `Node`
rather than only on `Asset` / `DataStore`. The spec's own path-finding
description allows crown jewels to be "critical data stores/accounts" (§3),
not just DataStores, so the tag needed to be settable on more than one node
type. Everything else follows the spec's per-type property tables exactly.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import (
    AssetType,
    CredentialType,
    DataClassification,
    FindingStatus,
    NodeType,
    PrivilegeLevel,
)

# ARRAY(String) on Postgres (native, indexable); JSON-encoded list on other
# dialects (e.g. SQLite in tests) — same DDL as before on Postgres, but lets
# the model layer be exercised against SQLite for fast local test runs.
StringList = JSON().with_variant(ARRAY(String), "postgresql")


class Node(Base):
    """Common base for every node in the attack-chain graph."""

    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    node_type: Mapped[NodeType] = mapped_column(
        String(32), nullable=False
    )

    # Path-finding tags. See design note above for why these live here
    # rather than on individual subtypes.
    is_entry_point: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_crown_jewel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Nullable so pre-Phase-6 data (and direct API/script usage that never
    # heard of engagements) keeps working — see app/models/engagement.py's
    # docstring for the "active engagement" default-assignment story.
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("engagements.id", ondelete="SET NULL"), nullable=True, index=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    outgoing_edges = relationship(
        "Edge",
        foreign_keys="Edge.source_node_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "Edge",
        foreign_keys="Edge.target_node_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_on": node_type,
        "polymorphic_identity": "node",
    }

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        label = getattr(self, "name", None) or getattr(self, "title", None) or self.id
        return f"<{type(self).__name__} {label!r}>"


class Asset(Node):
    """A domain, subdomain, IP, host, or cloud resource."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    asset_type: Mapped[AssetType] = mapped_column(String(32), nullable=False)
    in_scope: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tags: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)

    __mapper_args__ = {"polymorphic_identity": NodeType.ASSET.value}


class Service(Node):
    """A port/protocol on an Asset."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), nullable=False)
    banner: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)

    __mapper_args__ = {"polymorphic_identity": NodeType.SERVICE.value}


class WebApplication(Node):
    """An application running on a Service."""

    __tablename__ = "web_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    tech_stack: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)
    auth_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __mapper_args__ = {"polymorphic_identity": NodeType.WEB_APPLICATION.value}


class Endpoint(Node):
    """A specific route/page/API path."""

    __tablename__ = "endpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="GET")
    params: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)
    requires_auth: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    documented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __mapper_args__ = {"polymorphic_identity": NodeType.ENDPOINT.value}


class Credential(Node):
    """A password/token/key obtained during testing."""

    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )
    cred_type: Mapped[CredentialType] = mapped_column(String(32), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(256), nullable=True)
    obtained_via_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )

    __mapper_args__ = {"polymorphic_identity": NodeType.CREDENTIAL.value}


class Account(Node):
    """A user or service account."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )
    username: Mapped[str] = mapped_column(String(256), nullable=False)
    privilege_level: Mapped[PrivilegeLevel] = mapped_column(
        String(16), nullable=False, default=PrivilegeLevel.STANDARD.value
    )

    __mapper_args__ = {"polymorphic_identity": NodeType.ACCOUNT.value}


class DataStore(Node):
    """A database, bucket, or file share."""

    __tablename__ = "data_stores"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    data_classification: Mapped[DataClassification] = mapped_column(
        String(16), nullable=False, default=DataClassification.NONE.value
    )
    record_count_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __mapper_args__ = {"polymorphic_identity": NodeType.DATA_STORE.value}


class Finding(Node):
    """A vulnerability."""

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    cwe: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owasp_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Full CVSS v3 vector (e.g. "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H").
    # The score alone is a single number; the vector says *why* — including
    # Attack Complexity, which the ease_score formula needs and which was
    # previously a flat placeholder for every finding. Nuclei templates with
    # `cvss-metrics` supply this for free. See app/services/cvss.py.
    cvss_vector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exploit_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auth_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FindingStatus] = mapped_column(
        String(16), nullable=False, default=FindingStatus.OPEN.value
    )

    __mapper_args__ = {"polymorphic_identity": NodeType.FINDING.value}
