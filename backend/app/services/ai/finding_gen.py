"""AI-powered finding generator.

Generates structured, realistic pentest findings from asset context
(asset type, open ports, services, observed behaviour). Output is
advisory only — the analyst reviews, edits, and submits via the normal
manual finding form. Nothing is written to the database until the
analyst confirms.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Sequence

from pydantic import BaseModel, Field, field_validator

from app.services.ai.provider import AIProvider, AIResult, get_provider

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class GeneratedFinding(BaseModel):
    """A single generated finding ready for analyst review."""

    title: str = Field(max_length=512)
    description: str = Field(max_length=2000)
    severity: FindingSeverity
    cwe: str | None = Field(default=None, max_length=32)
    owasp_category: str | None = Field(default=None, max_length=128)
    cvss_score: float | None = Field(default=None, ge=0.0, le=10.0)
    cvss_vector: str | None = Field(default=None, max_length=128)
    exploit_public: bool = False
    auth_required: bool = True
    remediation: str = Field(max_length=2000)
    affected_assets: list[str] = Field(default_factory=list)
    evidence: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @field_validator(
        "affected_assets",
        "tags",
        "assumptions",
        mode="before",
    )
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


class GeneratedFindingSet(BaseModel):
    """Collection of findings generated for one asset / scan."""

    findings: list[GeneratedFinding]
    context_summary: str = Field(max_length=1000)
    model: str | None = None
    generated_at: datetime | None = None
    assumptions: list[str] = Field(default_factory=list)


# ── Service ──────────────────────────────────────────────────────────────


def _asset_context_section(node_type: str, properties: dict) -> str:
    """Build a structured context block from node properties."""
    lines: list[str] = []
    lines.append(f"Asset type: {node_type}")
    for key in (
        "name",
        "asset_type",
        "ip_address",
        "hostname",
        "path",
        "port",
        "service_name",
        "technology",
        "data_classification",
        "os",
        "version",
    ):
        val = properties.get(key)
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")
    return "\n".join(lines)


def build_finding_prompt(
    node_type: str,
    properties: dict,
    target_assets: Sequence[str] | None = None,
) -> tuple[str, str]:
    """Build the system + user prompts for finding generation."""
    system = (
        "You are a senior penetration tester writing realistic, evidence-based "
        "security findings. Output ONLY a JSON object — no markdown fences, no "
        "extra commentary. The JSON must match this schema exactly:\n"
        '{\n'
        '  "findings": [\n'
        '    {\n'
        '      "title": string,\n'
        '      "description": string,\n'
        '      "severity": "critical"|"high"|"medium"|"low"|"info",\n'
        '      "cwe": string|null,\n'
        '      "owasp_category": string|null,\n'
        '      "cvss_score": number|null (0-10),\n'
        '      "cvss_vector": string|null,\n'
        '      "exploit_public": boolean,\n'
        '      "auth_required": boolean,\n'
        '      "remediation": string,\n'
        '      "affected_assets": [string],\n'
        '      "evidence": string|null,\n'
        '      "tags": [string],\n'
        '      "assumptions": [string]\n'
        '    }\n'
        '  ],\n'
        '  "assumptions": [string]\n'
        '}\n'
        "Rules:\n"
        "1. Every finding MUST be realistic for the asset described — do not "
        "generate generic template findings.\n"
        "2. State assumptions explicitly (things you cannot observe).\n"
        "3. CWE IDs should be valid (e.g. 'CWE-79', 'CWE-89').\n"
        "4. OWASP categories should be 'A01:2021' style.\n"
        "5. CVSS vectors should be complete (e.g. 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H').\n"
        "6. severity must match the CVSS score range.\n"
        "7. auth_required is true if exploitation needs authenticated access.\n"
        "8. Generate 1-5 findings depending on the complexity of the asset.\n"
        "9. Output findings a pentester would actually report to a client.\n"
        "10. If you cannot generate realistic findings from the given context, "
        'return {"findings": [], "assumptions": ["insufficient context"]}.'
    )
    context = _asset_context_section(node_type, properties)
    user = f"Context:\n{context}\n"
    if target_assets:
        user += f"\nAdditional target context: {', '.join(target_assets)}\n"
    user += "\nGenerate findings for this asset."
    return system, user


@dataclass
class FindingGenOutcome:
    findings: list[GeneratedFinding] = field(default_factory=list)
    error: str | None = None
    model: str | None = None
    generated_at: datetime | None = None

    @property
    def ok(self) -> bool:
        return bool(self.findings) or self.error is None


def generate_findings(
    node_type: str,
    properties: dict,
    target_assets: Sequence[str] | None = None,
    provider: AIProvider | None = None,
) -> FindingGenOutcome:
    """Generate AI findings for an asset. Never raises."""
    provider = provider or get_provider()

    if not provider.is_configured:
        return FindingGenOutcome(
            error=provider.complete("", "").failure_message,
        )

    system, user = build_finding_prompt(node_type, properties, target_assets)

    from app.core.config import get_settings

    response = provider.complete(
        system, user, max_tokens=getattr(get_settings(), "ai_max_tokens", 3000)
    )

    if not response.ok:
        return FindingGenOutcome(error=response.failure_message, model=response.model)

    raw = response.text or ""
    if not raw.strip():
        return FindingGenOutcome(error="Empty response from AI provider", model=response.model)

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in response")
        data = json.loads(cleaned[start : end + 1])
        parsed = GeneratedFindingSet.model_validate(data)
    except Exception as exc:
        logger.warning("AI finding generation failed validation: %s — raw: %.200s", exc, raw)
        return FindingGenOutcome(
            error="The AI response didn't match the expected format. Please try again.",
            model=response.model,
        )

    return FindingGenOutcome(
        findings=parsed.findings,
        model=response.model,
        generated_at=datetime.now(timezone.utc),
    )
