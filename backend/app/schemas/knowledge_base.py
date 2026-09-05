"""Pydantic schemas for the knowledge base API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeBaseEntryBase(BaseModel):
    cwe_id: str | None = Field(default=None, description="CWE identifier, e.g. CWE-79")
    name: str = Field(..., description="Short name for the vulnerability type")
    description: str = Field(..., description="Detailed description")
    remediation: str = Field(default="", description="Remediation guidance")
    references: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    owasp_category: str | None = Field(default=None)
    severity_guidance: str | None = Field(default=None)


class KnowledgeBaseEntryCreate(KnowledgeBaseEntryBase):
    pass


class KnowledgeBaseEntryUpdate(BaseModel):
    cwe_id: str | None = None
    name: str | None = None
    description: str | None = None
    remediation: str | None = None
    references: list[str] | None = None
    tags: list[str] | None = None
    owasp_category: str | None = None
    severity_guidance: str | None = None


class KnowledgeBaseEntryResponse(KnowledgeBaseEntryBase):
    id: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class SimilarSearchRequest(BaseModel):
    cwe_id: str | None = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None)
    top_n: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.2, ge=0.0, le=1.0)


class SimilarSearchResponse(BaseModel):
    query_cwe: str | None
    query_tags: list[str]
    matches: list[dict]


class SimilarEntryResponse(BaseModel):
    entry_id: str
    cwe_id: str | None
    name: str
    score: float
    match_reason: str
