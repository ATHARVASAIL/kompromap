"""Pydantic schemas for node CRUD.

One Create/Read pair per node type (matching spec §4's per-type property
tables), joined into discriminated unions on `node_type` so a single
POST /api/nodes endpoint can accept any of the 8 types with proper
per-type validation.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AssetType,
    CredentialType,
    DataClassification,
    FindingStatus,
    NodeType,
    PrivilegeLevel,
)


class NodeCommon(BaseModel):
    """Fields every node create/update payload can set."""

    engagement_id: uuid.UUID | None = None  # defaults to the active engagement if omitted
    is_entry_point: bool = False
    is_crown_jewel: bool = False
    notes: str | None = None


class NodeReadCommon(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    engagement_id: uuid.UUID | None
    node_type: NodeType
    is_entry_point: bool
    is_crown_jewel: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --- Asset -------------------------------------------------------------


class AssetCreate(NodeCommon):
    node_type: Literal[NodeType.ASSET] = NodeType.ASSET
    name: str
    asset_type: AssetType
    in_scope: bool = True
    tags: list[str] = Field(default_factory=list)


class AssetUpdate(BaseModel):
    name: str | None = None
    asset_type: AssetType | None = None
    in_scope: bool | None = None
    tags: list[str] | None = None
    is_entry_point: bool | None = None
    is_crown_jewel: bool | None = None
    notes: str | None = None


class AssetRead(NodeReadCommon):
    node_type: Literal[NodeType.ASSET] = NodeType.ASSET
    name: str
    asset_type: AssetType
    in_scope: bool
    tags: list[str]


# --- Service -------------------------------------------------------------


class ServiceCreate(NodeCommon):
    node_type: Literal[NodeType.SERVICE] = NodeType.SERVICE
    # TCP/UDP ports are 1-65535; out-of-range values are always bad data.
    port: int = Field(ge=1, le=65535)
    protocol: str
    banner: str | None = None
    tech_stack: list[str] = Field(default_factory=list)


class ServiceUpdate(BaseModel):
    port: int | None = Field(default=None, ge=1, le=65535)
    protocol: str | None = None
    banner: str | None = None
    tech_stack: list[str] | None = None
    is_entry_point: bool | None = None
    is_crown_jewel: bool | None = None
    notes: str | None = None


class ServiceRead(NodeReadCommon):
    node_type: Literal[NodeType.SERVICE] = NodeType.SERVICE
    port: int
    protocol: str
    banner: str | None
    tech_stack: list[str]


# --- WebApplication --------------------------------------------------------


class WebApplicationCreate(NodeCommon):
    node_type: Literal[NodeType.WEB_APPLICATION] = NodeType.WEB_APPLICATION
    name: str
    base_url: str
    tech_stack: list[str] = Field(default_factory=list)
    auth_type: str | None = None


class WebApplicationUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    tech_stack: list[str] | None = None
    auth_type: str | None = None
    is_entry_point: bool | None = None
    is_crown_jewel: bool | None = None
    notes: str | None = None


class WebApplicationRead(NodeReadCommon):
    node_type: Literal[NodeType.WEB_APPLICATION] = NodeType.WEB_APPLICATION
    name: str
    base_url: str
    tech_stack: list[str]
    auth_type: str | None


# --- Endpoint -------------------------------------------------------------


class EndpointCreate(NodeCommon):
    node_type: Literal[NodeType.ENDPOINT] = NodeType.ENDPOINT
    path: str
    method: str = "GET"
    params: list[str] = Field(default_factory=list)
    requires_auth: bool | None = None
    documented: bool = False


class EndpointUpdate(BaseModel):
    path: str | None = None
    method: str | None = None
    params: list[str] | None = None
    requires_auth: bool | None = None
    documented: bool | None = None
    is_entry_point: bool | None = None
    is_crown_jewel: bool | None = None
    notes: str | None = None


class EndpointRead(NodeReadCommon):
    node_type: Literal[NodeType.ENDPOINT] = NodeType.ENDPOINT
    path: str
    method: str
    params: list[str]
    requires_auth: bool | None
    documented: bool


# --- Credential -------------------------------------------------------------


class CredentialCreate(NodeCommon):
    node_type: Literal[NodeType.CREDENTIAL] = NodeType.CREDENTIAL
    cred_type: CredentialType
    scope: str | None = None
    obtained_via_finding_id: uuid.UUID | None = None


class CredentialUpdate(BaseModel):
    cred_type: CredentialType | None = None
    scope: str | None = None
    obtained_via_finding_id: uuid.UUID | None = None
    is_entry_point: bool | None = None
    is_crown_jewel: bool | None = None
    notes: str | None = None


class CredentialRead(NodeReadCommon):
    node_type: Literal[NodeType.CREDENTIAL] = NodeType.CREDENTIAL
    cred_type: CredentialType
    scope: str | None
    obtained_via_finding_id: uuid.UUID | None


# --- Account -------------------------------------------------------------


class AccountCreate(NodeCommon):
    node_type: Literal[NodeType.ACCOUNT] = NodeType.ACCOUNT
    username: str
    privilege_level: PrivilegeLevel = PrivilegeLevel.STANDARD


class AccountUpdate(BaseModel):
    username: str | None = None
    privilege_level: PrivilegeLevel | None = None
    is_entry_point: bool | None = None
    is_crown_jewel: bool | None = None
    notes: str | None = None


class AccountRead(NodeReadCommon):
    node_type: Literal[NodeType.ACCOUNT] = NodeType.ACCOUNT
    username: str
    privilege_level: PrivilegeLevel


# --- DataStore -------------------------------------------------------------


class DataStoreCreate(NodeCommon):
    node_type: Literal[NodeType.DATA_STORE] = NodeType.DATA_STORE
    name: str
    data_classification: DataClassification = DataClassification.NONE
    record_count_estimate: int | None = None


class DataStoreUpdate(BaseModel):
    name: str | None = None
    data_classification: DataClassification | None = None
    record_count_estimate: int | None = None
    is_entry_point: bool | None = None
    is_crown_jewel: bool | None = None
    notes: str | None = None


class DataStoreRead(NodeReadCommon):
    node_type: Literal[NodeType.DATA_STORE] = NodeType.DATA_STORE
    name: str
    data_classification: DataClassification
    record_count_estimate: int | None


# --- Finding -------------------------------------------------------------


class FindingCreate(NodeCommon):
    node_type: Literal[NodeType.FINDING] = NodeType.FINDING
    title: str
    cwe: str | None = None
    owasp_category: str | None = None
    # CVSS v3 is defined as 0.0-10.0. Unbounded values would silently
    # corrupt severity banding (styles/tokens.ts severityFromCvss) and the
    # path-finding ease score, which normalizes by dividing by 10.
    cvss_score: float | None = Field(default=None, ge=0.0, le=10.0)
    exploit_public: bool = False
    auth_required: bool = True
    evidence: str | None = None
    status: FindingStatus = FindingStatus.OPEN


class FindingUpdate(BaseModel):
    title: str | None = None
    cwe: str | None = None
    owasp_category: str | None = None
    cvss_score: float | None = Field(default=None, ge=0.0, le=10.0)
    exploit_public: bool | None = None
    auth_required: bool | None = None
    evidence: str | None = None
    status: FindingStatus | None = None
    is_entry_point: bool | None = None
    is_crown_jewel: bool | None = None
    notes: str | None = None


class FindingRead(NodeReadCommon):
    node_type: Literal[NodeType.FINDING] = NodeType.FINDING
    title: str
    cwe: str | None
    owasp_category: str | None
    cvss_score: float | None
    exploit_public: bool
    auth_required: bool
    evidence: str | None
    status: FindingStatus


# --- unions for the generic /api/nodes endpoint -----------------------------

NodeCreate = Annotated[
    Union[
        AssetCreate,
        ServiceCreate,
        WebApplicationCreate,
        EndpointCreate,
        CredentialCreate,
        AccountCreate,
        DataStoreCreate,
        FindingCreate,
    ],
    Field(discriminator="node_type"),
]

NodeRead = Annotated[
    Union[
        AssetRead,
        ServiceRead,
        WebApplicationRead,
        EndpointRead,
        CredentialRead,
        AccountRead,
        DataStoreRead,
        FindingRead,
    ],
    Field(discriminator="node_type"),
]

READ_SCHEMA_BY_TYPE: dict[NodeType, type[NodeReadCommon]] = {
    NodeType.ASSET: AssetRead,
    NodeType.SERVICE: ServiceRead,
    NodeType.WEB_APPLICATION: WebApplicationRead,
    NodeType.ENDPOINT: EndpointRead,
    NodeType.CREDENTIAL: CredentialRead,
    NodeType.ACCOUNT: AccountRead,
    NodeType.DATA_STORE: DataStoreRead,
    NodeType.FINDING: FindingRead,
}

UPDATE_SCHEMA_BY_TYPE: dict[NodeType, type[BaseModel]] = {
    NodeType.ASSET: AssetUpdate,
    NodeType.SERVICE: ServiceUpdate,
    NodeType.WEB_APPLICATION: WebApplicationUpdate,
    NodeType.ENDPOINT: EndpointUpdate,
    NodeType.CREDENTIAL: CredentialUpdate,
    NodeType.ACCOUNT: AccountUpdate,
    NodeType.DATA_STORE: DataStoreUpdate,
    NodeType.FINDING: FindingUpdate,
}
