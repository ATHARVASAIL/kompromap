"""add findings.cvss_vector

Revision ID: 7c80a3a8874d
Revises: 24726b59aa26
Create Date: 2026-08-02

Stores the full CVSS v3 vector string alongside the numeric score, so the
path-finding model can derive real Attack Complexity instead of applying a
flat placeholder to every finding. Nullable — plenty of findings (manual
entry, Burp/ZAP exports) legitimately have no vector, and those keep using
the configured default.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7c80a3a8874d"
down_revision: Union[str, None] = "24726b59aa26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("cvss_vector", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "cvss_vector")
