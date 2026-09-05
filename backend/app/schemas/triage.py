"""Structured, validated AI triage output.

Application logic must never depend on free-form model text (spec §6). Two
reasons, and the second is the important one:

1. Models return malformed JSON, wrap it in markdown fences, omit fields,
   or emit an apology instead of an object.
2. **Validation is the real prompt-injection backstop.** Structural
   separation in `prompts.py` raises the cost of an injection; this is
   what bounds the damage. Even a fully successful injection can only
   produce a value from a fixed enum, a float in [0,1], and a bounded list
   of strings. It cannot make Kompromap take an action, mark a finding
   confirmed, or alter path-finding — those require an analyst.
"""
from __future__ import annotations

import json
import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator

# Bounds on list fields. A model looping and emitting 500 "assumptions"
# is a rendering problem and a cost problem; neither should reach the UI.
MAX_ITEMS = 12
MAX_ITEM_CHARS = 500


class TriageAssessment(str, Enum):
    LIKELY_VALID = "likely_valid"
    LIKELY_FALSE_POSITIVE = "likely_false_positive"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class TriageSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AITriageResult(BaseModel):
    """A validated AI assessment.

    Note what is *absent*: there is no "confirmed" value and no field that
    sets analyst state. The AI can say `likely_valid`; only a human sets
    `verification_status = confirmed`. That separation is deliberate and
    load-bearing — see `services/ai/triage.py`.
    """

    assessment: TriageAssessment
    confidence: float = Field(ge=0.0, le=1.0)
    severity: TriageSeverity
    reasoning_summary: str = Field(max_length=2000)
    evidence_supporting: list[str] = Field(default_factory=list)
    evidence_missing: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    recommended_validation: list[str] = Field(default_factory=list)
    potential_impact: list[str] = Field(default_factory=list)
    related_vulnerability_types: list[str] = Field(default_factory=list)

    @field_validator(
        "evidence_supporting",
        "evidence_missing",
        "assumptions",
        "recommended_validation",
        "potential_impact",
        "related_vulnerability_types",
        mode="before",
    )
    @classmethod
    def _coerce_list(cls, v):
        """Models sometimes return a bare string where a list was asked
        for. Accept it rather than discarding an otherwise good response."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v if x is not None and str(x).strip()]
        return []

    @field_validator(
        "evidence_supporting",
        "evidence_missing",
        "assumptions",
        "recommended_validation",
        "potential_impact",
        "related_vulnerability_types",
    )
    @classmethod
    def _bound_list(cls, v: list[str]) -> list[str]:
        return [item[:MAX_ITEM_CHARS] for item in v[:MAX_ITEMS]]

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        """Accept 87 or "87%" as 0.87 — a common model slip that would
        otherwise fail an otherwise-valid response."""
        if isinstance(v, str):
            v = v.strip().rstrip("%")
            try:
                v = float(v)
            except ValueError:
                return 0.0
        if isinstance(v, (int, float)) and v > 1.0:
            return min(float(v) / 100.0, 1.0)
        return v

    @property
    def is_low_confidence(self) -> bool:
        """Below this the UI foregrounds the caveats rather than the
        conclusion — a hedged answer presented confidently is worse than
        no answer."""
        return self.confidence < 0.5


class TriageParseError(ValueError):
    pass


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_triage_response(raw: str) -> AITriageResult:
    """Parse and validate a model response. Raises TriageParseError on
    anything unusable — callers surface that as "AI analysis unavailable"
    rather than showing the analyst a half-parsed object."""
    if not raw or not raw.strip():
        raise TriageParseError("empty response")

    text = _FENCE_RE.sub("", raw.strip())

    # Models sometimes prepend a sentence before the object. Take the
    # outermost braces rather than failing the whole response.
    if not text.lstrip().startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise TriageParseError("no JSON object found in response")
        text = text[start : end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TriageParseError(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise TriageParseError("response was not a JSON object")

    try:
        return AITriageResult.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise TriageParseError(f"response did not match schema: {exc}") from exc
