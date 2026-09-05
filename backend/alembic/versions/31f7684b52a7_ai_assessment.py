"""add findings.ai_assessment

Revision ID: 31f7684b52a7
Revises: 907f0af0a473
Create Date: 2026-09-04

Stores the AI triage assessment as validated JSON. Nullable — AI triage is
optional, every other feature works without it, and existing rows simply
have no assessment yet.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "31f7684b52a7"
down_revision: Union[str, None] = "907f0af0a473"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("ai_assessment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "ai_assessment")
