"""add knowledge_base table"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "33_knowledge_base"
down_revision = "32dedup_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cwe_id", sa.String(32), nullable=True, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=False, server_default=""),
        sa.Column("references", JSONB(), nullable=True, server_default="[]"),
        sa.Column("tags", JSONB(), nullable=True, server_default="[]"),
        sa.Column("owasp_category", sa.String(64), nullable=True),
        sa.Column("severity_guidance", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_knowledge_base_cwe_id", "knowledge_base", ["cwe_id"])
    op.create_index("ix_knowledge_base_owasp_category", "knowledge_base", ["owasp_category"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_base_owasp_category", table_name="knowledge_base")
    op.drop_index("ix_knowledge_base_cwe_id", table_name="knowledge_base")
    op.drop_table("knowledge_base")
