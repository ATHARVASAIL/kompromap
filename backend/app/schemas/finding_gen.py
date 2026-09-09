"""Schemas for the AI finding generator (Phase 4)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from app.services.ai.finding_gen import FindingSeverity


class FindingGenerateRequest(BaseModel):
    """Ask the AI to generate findings for a specific node."""
    node_id: str
    target_assets: list[str] = Field(default_factory=list)
    extra_context: str | None = Field(default=None, max_length=1000)


class GeneratedFindingRead(BaseModel):
    """A generated finding, ready for review."""
    title: str
    description: str
    severity: str
    cwe: str | None = None
    owasp_category: str | None = None
    cvss_score: float | None = Field(default=None, ge=0.0, le=10.0)
    cvss_vector: str | None = Field(default=None, max_length=128)
    exploit_public: bool = False
    auth_required: bool = True
    remediation: str = Field(max_length=2000)
    affected_assets: list[str] = Field(default_factory=list)
    evidence: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("affected_assets", "tags", "assumptions", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v if x is not None and str(x).strip()]
        return []

    @field_validator("cvss_score", mode="before")
    @classmethod
    def _coerce_cvss(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip().rstrip("%")
            try:
                v = float(v)
            except ValueError:
                return None
        if isinstance(v, (int, float)) and v > 10.0:
            return None
        return float(v)


class FindingGenerateResponse(BaseModel):
    """Returned findings, each labelled as advisory."""
    findings: list[GeneratedFindingRead]
    model: str | None = None
    generated_at: datetime | None = None
    assumptions: list[str] = Field(default_factory=list)
    note: str = "AI-generated findings are advisory only. Edit and submit via the manual finding form."
