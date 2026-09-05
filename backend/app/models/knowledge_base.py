"""Knowledge base model for storing vulnerability reference data.

Each entry represents a known vulnerability type (typically a CWE) with
structured remediation guidance, references, and tags. The similarity
search uses exact CWE matching, tag overlap (Jaccard), and keyword
matching on descriptions.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class KnowledgeBaseEntry(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[uuid.UUID] = mapped_column(
        "id", primary_key=True, default=uuid.uuid4
    )
    cwe_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True, unique=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    references: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, default=list
    )
    tags: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, default=list
    )
    owasp_category: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    severity_guidance: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<KBEntry {self.cwe_id or self.name!r}>"
