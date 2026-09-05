"""add dedup_scans and merge_candidates tables

Revision ID: 32dedup_tables
Revises: 31f7684b52a7
Create Date: 2026-09-05

Supports the Phase 2 deduplication engine:
- ``dedup_scans`` — one record per scan run (engagement, threshold, signals used, outcome)
- ``merge_candidates`` — pairs of findings that look like duplicates, with signal-level
  similarity scores and analyst action tracking (pending / merge / keep_separate / mark_duplicate)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "32dedup_tables"
down_revision: Union[str, None] = "31f7684b52a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dedup_scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("similarity_threshold", sa.Float(), nullable=False),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("candidates_found", sa.Integer(), nullable=False),
        sa.Column("candidates_filtered", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dedup_scans_engagement_id", "dedup_scans", ["engagement_id"], unique=False)

    op.create_table(
        "merge_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("finding_a_id", sa.Uuid(), nullable=False),
        sa.Column("finding_b_id", sa.Uuid(), nullable=False),
        sa.Column("signal_scores", sa.JSON(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("high_impact", sa.Boolean(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("kept_id", sa.Uuid(), nullable=True),
        sa.Column("analyst_note", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["dedup_scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merge_candidates_scan_id", "merge_candidates", ["scan_id"], unique=False)
    op.create_index("ix_merge_candidates_finding_a_id", "merge_candidates", ["finding_a_id"], unique=False)
    op.create_index("ix_merge_candidates_finding_b_id", "merge_candidates", ["finding_b_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_merge_candidates_finding_b_id", table_name="merge_candidates")
    op.drop_index("ix_merge_candidates_finding_a_id", table_name="merge_candidates")
    op.drop_index("ix_merge_candidates_scan_id", table_name="merge_candidates")
    op.drop_table("merge_candidates")
    op.drop_index("ix_dedup_scans_engagement_id", table_name="dedup_scans")
    op.drop_table("dedup_scans")
