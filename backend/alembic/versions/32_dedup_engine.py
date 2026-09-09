"""dedup engine — dedup_scans and merge_candidates tables (Phase 2)

Revision ID: 32_dedup_engine
Revises: 31f7684b52a7
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "32_dedup_engine"
down_revision: Union[str, None] = "31f7684b52a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dedup_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("total_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_confidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("merged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dismissed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settings_snapshot", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_dedup_scans_engagement_id", "dedup_scans", ["engagement_id"])

    op.create_table(
        "merge_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dedup_scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url_similarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("endpoint_similarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("param_similarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cwe_similarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("request_similarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("response_similarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("threshold_used", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_merge_candidates_engagement_id", "merge_candidates", ["engagement_id"])
    op.create_index("ix_merge_candidates_finding_a_id", "merge_candidates", ["finding_a_id"])
    op.create_index("ix_merge_candidates_finding_b_id", "merge_candidates", ["finding_b_id"])
    op.create_index("ix_merge_candidates_status", "merge_candidates", ["status"])


def downgrade() -> None:
    op.drop_table("merge_candidates")
    op.drop_table("dedup_scans")
