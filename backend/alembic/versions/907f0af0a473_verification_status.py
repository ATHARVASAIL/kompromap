"""add findings verification status

Revision ID: 907f0af0a473
Revises: 7c80a3a8874d
Create Date: 2026-08-03

Tracks whether a tester has confirmed a finding is real, separately from
`status` (which tracks remediation). Existing rows default to
'unverified', which is the honest starting state — nothing that was
already imported has been triaged.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "907f0af0a473"
down_revision: Union[str, None] = "7c80a3a8874d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column(
            "verification_status",
            sa.String(20),
            nullable=False,
            server_default="unverified",
        ),
    )
    op.add_column("findings", sa.Column("verification_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "verification_note")
    op.drop_column("findings", "verification_status")
