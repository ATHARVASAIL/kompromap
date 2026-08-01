import uuid
from typing import Literal

from pydantic import BaseModel


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
