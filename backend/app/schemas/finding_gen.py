"""Structured output schema for AI-generated finding descriptions.

Same structural-separation / output-validation defence the triage module
uses: the model only sees scanner data, and its response is validated
against a fixed schema before anything reaches the report.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, field_validator

MAX_ITEMS = 8
MAX_ITEM_CHARS = 500
MAX_DESC_CHARS = 3000


class GeneratedFinding(BaseModel):
    """An AI-generated description for an existing finding."""

    title: str = Field(max_length=200, description="A concise, specific title for the finding.")
    description: str = Field(max_length=MAX_DESC_CHARS, description="Technical description of the vulnerability, how it was identified, and why it matters.")
    remediation_steps: list[str] = Field(default_factory=list, description="Ordered steps to remediate. Start with the most impactful.")
    references: list[str] = Field(default_factory=list, description="Authoritative URLs: CWE, OWASP, NVD, vendor advisories.")
    confidence: float = Field(ge=0.0, le=1.0, description="How confident the model is in this description given the evidence provided.")

    @field_validator("remediation_steps", "references", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v if x is not None and str(x).strip()]
        return []

    @field_validator("remediation_steps", "references")
    @classmethod
    def _bound_list(cls, v: list[str]) -> list[str]:
        return [item[:MAX_ITEM_CHARS] for item in v[:MAX_ITEMS]]

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        if isinstance(v, str):
            v = v.strip().rstrip("%")
            try:
                v = float(v)
            except ValueError:
                return 0.0
        if isinstance(v, (int, float)) and v > 1.0:
            return min(float(v) / 100.0, 1.0)
        return float(v)


class GenerationParseError(ValueError):
    pass


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_generation_response(raw: str) -> GeneratedFinding:
    """Parse and validate a model response. Raises GenerationParseError on
    anything unusable."""
    if not raw or not raw.strip():
        raise GenerationParseError("empty response")

    text = _FENCE_RE.sub("", raw.strip())

    if not text.lstrip().startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise GenerationParseError("no JSON object found in response")
        text = text[start : end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GenerationParseError(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise GenerationParseError("response was not a JSON object")

    try:
        return GeneratedFinding.model_validate(data)
    except Exception as exc:
        raise GenerationParseError(f"response did not match schema: {exc}") from exc
