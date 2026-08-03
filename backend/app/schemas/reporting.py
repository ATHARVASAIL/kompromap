import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.pathfind import ScoringWeightsInput


class ChainRequest(BaseModel):
    node_ids: list[uuid.UUID]


class NarrativeResponse(BaseModel):
    narrative: str
    narrative_source: Literal["llm", "template"]


class ExportRequest(BaseModel):
    node_ids: list[uuid.UUID]
    narrative: str | None = None  # reuse an already-generated narrative if provided
    format: Literal["markdown", "json"] = "markdown"


class ExportResponse(BaseModel):
    format: Literal["markdown", "json"]
    narrative_source: Literal["llm", "template"]
    content: str | None = None  # populated for format=markdown
    data: dict | None = None  # populated for format=json


class EngagementReportRequest(BaseModel):
    """Request a full engagement report."""

    engagement_id: uuid.UUID | None = Field(
        default=None, description="Defaults to the active engagement."
    )
    format: Literal["json", "markdown", "html"] = "json"
    include_narratives: bool = Field(
        default=False,
        description="Generate a prose narrative per chain. Slower, and uses the "
        "Anthropic API if a key is configured (falls back to a template otherwise).",
    )
    weights: ScoringWeightsInput | None = None


class EngagementReportResponse(BaseModel):
    format: Literal["json", "markdown", "html"]
    # Markdown/HTML come back as text; JSON as a structured object.
    content: str | None = None
    data: dict | None = None
