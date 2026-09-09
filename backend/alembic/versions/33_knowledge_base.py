"""knowledge base — knowledge_base table (Phase 5)

Revision ID: 33_knowledge_base
Revises: 32_dedup_engine
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "33_knowledge_base"
down_revision: Union[str, None] = "32_dedup_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("reference_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column("mitigations", sa.Text(), nullable=True),
        sa.Column("references", sa.Text(), nullable=True),
    )
    op.create_index("ix_knowledge_base_source", "knowledge_base", ["source"])
    op.create_index("ix_knowledge_base_reference_id", "knowledge_base", ["reference_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_base_reference_id", table_name="knowledge_base")
    op.drop_index("ix_knowledge_base_source", table_name="knowledge_base")
    op.drop_table("knowledge_base")
